"""Persistent project memory — logs everything for cross-session retrieval.

Stored in .orchestra/ inside the project root:
  chat_log.jsonl      — full Brain chat history (timestamped)
  decisions.md        — architectural decisions with rationale
  project_log.jsonl   — chronological event log (tasks, file changes)

On new session start, the context loader reads these and injects
a summary into the Brain's system prompt so it has full project context.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from orchestra.config import get_orchestra_dir


class ProjectMemory:
    """Persistent project memory across sessions."""

    def __init__(self, project_root: Path) -> None:
        self._root = project_root
        self._dir = get_orchestra_dir(project_root)
        self._chat_log = self._dir / "chat_log.jsonl"
        self._decisions_log = self._dir / "decisions.md"
        self._project_log = self._dir / "project_log.jsonl"

        # Initialize decisions file with header if new
        if not self._decisions_log.exists():
            self._decisions_log.write_text("# Architectural Decisions Log\n\n")

    # ── Chat Log ───────────────────────────────────────────────────────────

    def log_chat(self, role: str, content: str, session_id: str = "") -> None:
        """Append a chat message to the persistent log."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "role": role,
            "content": content,
        }
        with open(self._chat_log, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_chat_history(self, last_n: int = 50) -> list[dict]:
        """Retrieve recent chat messages across all sessions."""
        if not self._chat_log.exists():
            return []
        lines = self._chat_log.read_text().strip().split("\n")
        entries = []
        for line in lines[-last_n:]:
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries

    # ── Decision Log ───────────────────────────────────────────────────────

    def log_decision(self, title: str, decision: str, rationale: str) -> None:
        """Record an architectural decision."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n## [{timestamp}] {title}\n\n**Decision:** {decision}\n\n**Rationale:** {rationale}\n\n---\n"
        with open(self._decisions_log, "a") as f:
            f.write(entry)

        # Also log as a project event
        self.log_event("decision", f"{title}: {decision}")

    def get_decisions(self) -> str:
        """Return the full decisions log as markdown."""
        if not self._decisions_log.exists():
            return ""
        return self._decisions_log.read_text()

    # ── Project Event Log ──────────────────────────────────────────────────

    def log_event(self, event_type: str, description: str, metadata: Optional[dict] = None) -> None:
        """Log a project event (task queued, completed, file created, etc)."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "description": description,
        }
        if metadata:
            entry["metadata"] = metadata
        with open(self._project_log, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_recent_events(self, last_n: int = 30) -> list[dict]:
        """Retrieve recent project events."""
        if not self._project_log.exists():
            return []
        lines = self._project_log.read_text().strip().split("\n")
        entries = []
        for line in lines[-last_n:]:
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries

    # ── Context Loader (for new sessions) ──────────────────────────────────

    def build_session_context(self) -> str:
        """Build a context summary for the Brain at session start.

        Reads all logs and produces a condensed summary so the Brain
        knows everything about the project from previous sessions.
        """
        parts = []

        # Project files overview
        file_list = []
        for p in sorted(self._root.rglob("*")):
            if p.is_file() and not any(
                part.startswith(".") for part in p.relative_to(self._root).parts
            ):
                rel = str(p.relative_to(self._root))
                size = p.stat().st_size
                file_list.append(f"  {rel} ({size}B)")
        if file_list:
            parts.append("## Current Project Files\n" + "\n".join(file_list[:50]))

        # Decisions
        decisions = self.get_decisions()
        if decisions and len(decisions) > 50:
            parts.append(f"## Architectural Decisions\n{decisions}")

        # Recent events
        events = self.get_recent_events(20)
        if events:
            event_lines = []
            for e in events:
                ts = e["timestamp"][:16]
                event_lines.append(f"  [{ts}] {e['type']}: {e['description']}")
            parts.append("## Recent Project Activity\n" + "\n".join(event_lines))

        # Recent chat summary (last 20 exchanges)
        chats = self.get_chat_history(20)
        if chats:
            chat_lines = []
            for c in chats:
                ts = c["timestamp"][:16]
                role = c["role"]
                # Truncate long messages
                content = c["content"][:200] + "..." if len(c["content"]) > 200 else c["content"]
                chat_lines.append(f"  [{ts}] {role}: {content}")
            parts.append("## Recent Conversation History\n" + "\n".join(chat_lines))

        # PLAN.md if it exists
        plan_path = self._root / "PLAN.md"
        if plan_path.exists():
            parts.append(f"## Implementation Plan\n{plan_path.read_text(errors='replace')}")

        if not parts:
            return "(New project — no previous session data)"

        return "\n\n".join(parts)
