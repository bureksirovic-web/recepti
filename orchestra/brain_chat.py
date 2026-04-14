"""Brain Chat — interactive planning + autonomous review loop.

Two modes:
  Chat mode:   User actively talks to Brain, which emits structured tasks
  Review mode: When user is idle >30s, Brain autonomously reviews code
               against the implementation plan and adds fix/improvement tasks

All conversations and decisions are persisted to .orchestra/ for
cross-session retrieval via ProjectMemory.
"""

import json
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from orchestra.config import (
    API_KEY,
    BRAIN_BASE_URL,
    BRAIN_IDLE_THRESHOLD_S,
    BRAIN_MODEL,
    BRAIN_REVIEW_INTERVAL_S,
)
from orchestra.llm_client import chat_completion
from orchestra.memory import ProjectMemory
from orchestra.task_queue import TaskQueue

# ── System Prompts ─────────────────────────────────────────────────────────

BRAIN_CHAT_SYSTEM = """\
You are the Architect — a senior engineer planning and coordinating software development.

You are part of a dual-GPU coding pipeline:
- YOU (Brain) plan and design on GPU0
- A Coder agent on GPU1 automatically executes your tasks

When you want the Coder to do something, emit a task block like this:

```task
{
  "action": "create_file",
  "path": "src/main.py",
  "description": "Create the main FastAPI entry point with health check endpoint and CORS middleware",
  "context_files": ["requirements.txt"],
  "priority": 1
}
```

Available actions: create_file, edit_file, delete_file, run_command
Priority: 1 (highest) to 9 (lowest)

For run_command tasks, put the command in the "description" field.

Rules:
- Break complex work into small, atomic tasks (one file per task)
- Set appropriate priority so tasks execute in dependency order
- Include context_files that the Coder should read for reference
- You can emit multiple task blocks in a single response
- Between tasks, explain your reasoning and plan to the user
- Always provide clear, specific descriptions — the Coder only sees the task block
"""

BRAIN_REVIEW_SYSTEM = """\
You are the Architect reviewing a codebase. Analyze the current state of the project \
against the implementation plan and identify what needs to be done next.

For each issue or gap you find, emit a task block:

```task
{
  "action": "create_file" or "edit_file",
  "path": "relative/path/to/file",
  "description": "Detailed description of what to create or change",
  "context_files": ["files/to/reference"],
  "priority": 5
}
```

Rules:
- Only emit tasks for REAL issues — do not invent problems
- Check if a task already exists in the recent task list before creating duplicates
- Focus on: missing files, incomplete implementations, bugs, missing error handling
- Do NOT emit tasks for style/formatting issues
- Limit to at most 3 tasks per review cycle
"""


def _parse_task_blocks(text: str) -> list[dict]:
    """Extract task JSON blocks from Brain response text."""
    tasks = []
    pattern = r"```task\s*\n(.*?)```"
    for match in re.finditer(pattern, text, re.DOTALL):
        try:
            data = json.loads(match.group(1).strip())
            # Validate required fields
            if "action" in data and "description" in data:
                tasks.append(data)
        except json.JSONDecodeError:
            continue
    return tasks


class BrainChat:
    """Interactive chat with Brain + autonomous review loop."""

    def __init__(self, project_root: Path, queue: TaskQueue, memory: ProjectMemory) -> None:
        self._project_root = project_root
        self._queue = queue
        self._memory = memory
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Build system prompt with session context from previous sessions
        session_context = memory.build_session_context()
        system_prompt = BRAIN_CHAT_SYSTEM
        if session_context and "(New project" not in session_context:
            system_prompt += f"\n\n## Previous Session Context\n{session_context}"

        self._chat_history: list[dict] = [{"role": "system", "content": system_prompt}]
        self._last_user_input_time: float = time.time()
        self._review_thread: Optional[threading.Thread] = None
        self._running = False
        self._review_active = False
        self._lock = threading.Lock()

        memory.log_event("session_start", f"New session {self._session_id}")

    def start(self) -> None:
        """Start the review loop thread and the interactive chat."""
        self._running = True
        self._review_thread = threading.Thread(
            target=self._review_loop, daemon=True, name="brain-review"
        )
        self._review_thread.start()
        self._chat_loop()

    def stop(self) -> None:
        self._running = False

    # ── Interactive Chat ───────────────────────────────────────────────────

    def _chat_loop(self) -> None:
        """Main interactive chat loop."""
        # Provide initial project context
        plan_path = self._project_root / "PLAN.md"
        if plan_path.exists():
            plan_content = plan_path.read_text(errors="replace")
            self._chat_history.append(
                {
                    "role": "user",
                    "content": f"Here is the current implementation plan:\n\n{plan_content}\n\nI'm ready to work. What should we start with?",
                }
            )
        else:
            self._chat_history.append(
                {
                    "role": "user",
                    "content": "This is a new project. No implementation plan exists yet. Let's start planning.",
                }
            )

        # Get initial Brain response
        self._get_brain_response()

        while self._running:
            try:
                user_input = input("\n\033[1;36m🧠 You → Brain:\033[0m ")
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input.strip():
                continue

            # Special commands
            if user_input.strip().startswith("/"):
                if self._handle_command(user_input.strip()):
                    continue

            with self._lock:
                self._last_user_input_time = time.time()
                self._review_active = False

            self._chat_history.append({"role": "user", "content": user_input})
            self._memory.log_chat("user", user_input, self._session_id)
            self._get_brain_response()

    def _get_brain_response(self) -> None:
        """Call Brain and handle the response (parse tasks, display text)."""
        print("\n\033[1;33m🧠 Brain:\033[0m ", end="", flush=True)

        try:
            full_response = ""
            for chunk in chat_completion(
                BRAIN_BASE_URL,
                BRAIN_MODEL,
                self._chat_history,
                api_key=API_KEY,
                temperature=0.6,
                stream=True,
            ):
                print(chunk, end="", flush=True)
                full_response += chunk

            print()  # newline after streaming

            self._chat_history.append({"role": "assistant", "content": full_response})
            self._memory.log_chat("assistant", full_response, self._session_id)

            # Parse and enqueue tasks
            tasks = _parse_task_blocks(full_response)
            for t in tasks:
                task_id = self._queue.add_task(
                    action=t["action"],
                    path=t.get("path", ""),
                    description=t["description"],
                    context_files=t.get("context_files"),
                    priority=t.get("priority", 5),
                    source="brain_chat",
                )
                print(
                    f"  \033[1;32m📋 Task #{task_id} queued: [{t['action']}] {t.get('path', t['description'][:50])}\033[0m"
                )
                self._memory.log_event(
                    "task_queued",
                    f"#{task_id} [{t['action']}] {t.get('path', t['description'][:50])}",
                    {"source": "brain_chat"},
                )

        except Exception as e:
            print(f"\n\033[1;31m❌ Brain error: {e}\033[0m")

    def _handle_command(self, cmd: str) -> bool:
        """Handle slash commands. Returns True if command was handled."""
        if cmd == "/status":
            counts = self._queue.get_counts()
            print(
                f"\n📊 Tasks: ⏳{counts['pending']} 🔧{counts['in_progress']} ✅{counts['done']} ❌{counts['failed']}"
            )
            return True
        elif cmd == "/tasks":
            recent = self._queue.get_recent(10)
            print("\n📋 Recent tasks:")
            for t in recent:
                print(f"  {t.to_display()}")
            return True
        elif cmd.startswith("/decision "):
            # Log a decision: /decision Title | Decision text | Rationale
            parts = cmd[10:].split("|", 2)
            if len(parts) == 3:
                self._memory.log_decision(parts[0].strip(), parts[1].strip(), parts[2].strip())
                print("  \033[1;32m📝 Decision logged\033[0m")
            else:
                print("  Usage: /decision Title | Decision | Rationale")
            return True
        elif cmd == "/decisions":
            print(self._memory.get_decisions())
            return True
        elif cmd == "/log":
            events = self._memory.get_recent_events(15)
            print("\n📜 Recent project events:")
            for e in events:
                ts = e["timestamp"][:16]
                print(f"  [{ts}] {e['type']}: {e['description']}")
            return True
        elif cmd == "/help":
            print("\n  /status     — Task counts")
            print("  /tasks      — Recent tasks")
            print("  /decision   — Log decision: /decision Title | Decision | Rationale")
            print("  /decisions  — Show all decisions")
            print("  /log        — Recent project events")
            print("  /help       — This help")
            print("  Ctrl+C      — Exit")
            return True
        return False

    # ── Autonomous Review Loop ─────────────────────────────────────────────

    def _review_loop(self) -> None:
        """Background thread: when user is idle, Brain reviews codebase."""
        while self._running:
            time.sleep(5)  # Check every 5 seconds

            with self._lock:
                idle_time = time.time() - self._last_user_input_time
                if idle_time < BRAIN_IDLE_THRESHOLD_S:
                    continue
                if self._review_active:
                    # Already in review mode, wait for the interval
                    continue
                self._review_active = True

            try:
                self._run_review_cycle()
            except Exception:
                pass  # Don't crash the review thread

            # Wait before next review
            for _ in range(BRAIN_REVIEW_INTERVAL_S):
                if not self._running:
                    return
                with self._lock:
                    # If user started chatting, stop waiting
                    if not self._review_active:
                        break
                time.sleep(1)

            with self._lock:
                self._review_active = False

    def _run_review_cycle(self) -> None:
        """Execute one review cycle: scan code, identify gaps, emit tasks."""
        # Gather project state
        plan_content = ""
        plan_path = self._project_root / "PLAN.md"
        if plan_path.exists():
            plan_content = plan_path.read_text(errors="replace")

        # Get list of project files
        file_list = []
        for p in sorted(self._project_root.rglob("*")):
            if p.is_file() and not any(
                part.startswith(".") for part in p.relative_to(self._project_root).parts
            ):
                rel = str(p.relative_to(self._project_root))
                file_list.append(rel)

        # Get recent tasks to avoid duplicates
        recent = self._queue.get_recent(20)
        recent_summary = "\n".join(
            f"  - [{t.status}] {t.action}: {t.path or t.description[:60]}" for t in recent
        )

        # Build review prompt
        messages = [
            {"role": "system", "content": BRAIN_REVIEW_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"## Implementation Plan\n{plan_content or '(no plan yet)'}\n\n"
                    f"## Project Files\n{chr(10).join(file_list) or '(empty project)'}\n\n"
                    f"## Recent Tasks\n{recent_summary or '(no tasks yet)'}\n\n"
                    "Review the project state and identify what needs to be done. "
                    "Emit task blocks for any gaps or issues you find."
                ),
            },
        ]

        response = chat_completion(
            BRAIN_BASE_URL,
            BRAIN_MODEL,
            messages,
            api_key=API_KEY,
            temperature=0.3,
            max_tokens=4096,
        )
        assert isinstance(response, str)

        tasks = _parse_task_blocks(response)
        for t in tasks:
            task_id = self._queue.add_task(
                action=t["action"],
                path=t.get("path", ""),
                description=t["description"],
                context_files=t.get("context_files"),
                priority=t.get("priority", 5),
                source="brain_review",
            )
            print(
                f"\n  \033[1;35m🔍 Review task #{task_id}: [{t['action']}] {t.get('path', t['description'][:50])}\033[0m"
            )
            self._memory.log_event(
                "task_queued",
                f"#{task_id} [{t['action']}] {t.get('path', t['description'][:50])}",
                {"source": "brain_review"},
            )
