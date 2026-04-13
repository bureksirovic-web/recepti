"""Coder Worker — delegates all coding to Aider.

Runs as a background thread. For each task:
  1. Claims it from the queue
  2. Shells out to Aider with --message (non-interactive mode)
  3. Aider handles: code generation, diffs, git commits, repo map
  4. Reports result back to the queue

Aider is the battle-tested coding engine. Orchestra just coordinates.
"""

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from orchestra.config import (
    CODER_BASE_URL,
    CODER_MODEL,
    API_KEY,
    CODER_POLL_INTERVAL_S,
)
from orchestra.task_queue import TaskQueue, Task, TaskAction
from orchestra.memory import ProjectMemory

# Path to aider binary
AIDER_BIN = "/home/tomi/aider-env/bin/aider"


def _build_aider_command(task: Task, project_root: Path) -> list[str]:
    """Build the Aider CLI command for a given task."""
    cmd = [
        AIDER_BIN,
        "--model", f"openai/{CODER_MODEL}",
        "--openai-api-key", API_KEY,
        "--openai-api-base", CODER_BASE_URL,
        "--no-show-model-warnings",
        "--yes-always",          # Auto-accept all changes
        "--auto-commits",        # Git commit each change
        "--no-suggest-shell-commands",
        "--no-pretty",           # Clean output for logging
        "--analytics-disable",
    ]

    # Add context files
    for ctx_file in task.context_files:
        full = project_root / ctx_file
        if full.exists():
            cmd.extend(["--read", str(full)])

    # Add the target file if it's a file operation
    if task.path and task.action in (TaskAction.CREATE_FILE, TaskAction.EDIT_FILE):
        cmd.extend(["--file", str(project_root / task.path)])

    # Build the message based on action type
    if task.action == TaskAction.CREATE_FILE:
        message = f"Create the file `{task.path}` with the following requirements:\n\n{task.description}"
    elif task.action == TaskAction.EDIT_FILE:
        message = f"Edit the file `{task.path}` with the following changes:\n\n{task.description}"
    elif task.action == TaskAction.DELETE_FILE:
        message = f"Delete the file `{task.path}`. Reason: {task.description}"
    elif task.action == TaskAction.RUN_COMMAND:
        message = f"Run this command and fix any issues: {task.description}"
    else:
        message = task.description

    cmd.extend(["--message", message])

    return cmd


class CoderWorker:
    """Background worker that polls the task queue and delegates to Aider."""

    def __init__(self, project_root: Path, queue: TaskQueue, memory: ProjectMemory) -> None:
        self._project_root = project_root
        self._queue = queue
        self._memory = memory
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_task: Optional[Task] = None
        self._lock = threading.Lock()

    @property
    def current_task(self) -> Optional[Task]:
        with self._lock:
            return self._current_task

    def start(self) -> None:
        """Start the worker thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="coder-worker")
        self._thread.start()

    def stop(self) -> None:
        """Signal the worker to stop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                task = self._queue.claim_task()
                if task is None:
                    time.sleep(CODER_POLL_INTERVAL_S)
                    continue

                with self._lock:
                    self._current_task = task

                self._execute_task(task)

                with self._lock:
                    self._current_task = None

            except Exception as e:
                if self._current_task:
                    self._queue.fail_task(self._current_task.id, f"Worker error: {e}")
                with self._lock:
                    self._current_task = None
                time.sleep(CODER_POLL_INTERVAL_S)

    def _execute_task(self, task: Task) -> None:
        """Execute a task by shelling out to Aider."""
        cmd = _build_aider_command(task, self._project_root)

        print(f"\n  \033[1;34m🔧 Coder executing task #{task.id}: [{task.action}] {task.path or task.description[:50]}\033[0m")

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self._project_root),
                capture_output=True,
                text=True,
                timeout=600,  # 10 min max per task
                env={**os.environ, "OPENAI_API_KEY": API_KEY},
            )

            output = result.stdout[-1000:] if result.stdout else ""
            errors = result.stderr[-500:] if result.stderr else ""

            if result.returncode == 0:
                self._queue.complete_task(task.id, f"Aider completed successfully.\n{output}")
                self._memory.log_event("task_done", f"#{task.id} [{task.action}] {task.path or task.description[:50]}")
                print(f"  \033[1;32m✅ Task #{task.id} done\033[0m")
            else:
                self._queue.fail_task(task.id, f"Aider exit {result.returncode}:\n{errors}\n{output}")
                self._memory.log_event("task_failed", f"#{task.id} [{task.action}] exit {result.returncode}")
                print(f"  \033[1;31m❌ Task #{task.id} failed (exit {result.returncode})\033[0m")

        except subprocess.TimeoutExpired:
            self._queue.fail_task(task.id, "Aider timed out (600s)")
            print(f"  \033[1;31m⏰ Task #{task.id} timed out\033[0m")
        except FileNotFoundError:
            self._queue.fail_task(task.id, f"Aider not found at {AIDER_BIN}")
            print(f"  \033[1;31m❌ Aider binary not found\033[0m")
