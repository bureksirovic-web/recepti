"""SQLite-backed task queue with WAL mode for concurrent access.

Task lifecycle: pending → in_progress → done / failed
"""

import json
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


class TaskAction(str, Enum):
    CREATE_FILE = "create_file"
    EDIT_FILE = "edit_file"
    DELETE_FILE = "delete_file"
    RUN_COMMAND = "run_command"


@dataclass
class Task:
    id: int = 0
    action: str = ""
    path: str = ""
    description: str = ""
    context_files: list[str] = field(default_factory=list)
    priority: int = 5
    status: str = TaskStatus.PENDING
    result: str = ""
    created_at: float = 0.0
    started_at: float = 0.0
    finished_at: float = 0.0
    source: str = "brain_chat"  # brain_chat | brain_review

    def to_display(self) -> str:
        """Short one-line display string."""
        emoji = {"pending": "⏳", "in_progress": "🔧", "done": "✅", "failed": "❌"}
        return f"{emoji.get(self.status, '?')} [{self.action}] {self.path or self.description[:60]}"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT NOT NULL,
    path        TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    context_files TEXT NOT NULL DEFAULT '[]',
    priority    INTEGER NOT NULL DEFAULT 5,
    status      TEXT NOT NULL DEFAULT 'pending',
    result      TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL,
    started_at  REAL NOT NULL DEFAULT 0,
    finished_at REAL NOT NULL DEFAULT 0,
    source      TEXT NOT NULL DEFAULT 'brain_chat'
);
CREATE INDEX IF NOT EXISTS idx_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_priority ON tasks(priority);
"""


class TaskQueue:
    """Thread-safe SQLite task queue using WAL mode."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def add_task(
        self,
        action: str,
        path: str = "",
        description: str = "",
        context_files: Optional[list[str]] = None,
        priority: int = 5,
        source: str = "brain_chat",
    ) -> int:
        """Insert a new task and return its ID."""
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO tasks (action, path, description, context_files,
                   priority, status, created_at, source)
                   VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (
                    action,
                    path,
                    description,
                    json.dumps(context_files or []),
                    priority,
                    time.time(),
                    source,
                ),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def claim_task(self) -> Optional[Task]:
        """Atomically claim the highest-priority pending task."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT * FROM tasks WHERE status = 'pending'
                   ORDER BY priority ASC, created_at ASC LIMIT 1"""
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE tasks SET status = 'in_progress', started_at = ? WHERE id = ?",
                (time.time(), row["id"]),
            )
            return self._row_to_task(row, status_override="in_progress")

    def complete_task(self, task_id: int, result: str = "") -> None:
        """Mark a task as done."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET status = 'done', result = ?, finished_at = ? WHERE id = ?",
                (result, time.time(), task_id),
            )

    def fail_task(self, task_id: int, error: str = "") -> None:
        """Mark a task as failed."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET status = 'failed', result = ?, finished_at = ? WHERE id = ?",
                (error, time.time(), task_id),
            )

    def get_counts(self) -> dict[str, int]:
        """Return counts by status."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status"
            ).fetchall()
            counts = {s.value: 0 for s in TaskStatus}
            for row in rows:
                counts[row["status"]] = row["cnt"]
            return counts

    def get_recent(self, limit: int = 10) -> list[Task]:
        """Return recent tasks ordered by creation time."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [self._row_to_task(r) for r in rows]

    def get_active_task(self) -> Optional[Task]:
        """Return the currently in-progress task, if any."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE status = 'in_progress' LIMIT 1"
            ).fetchone()
            return self._row_to_task(row) if row else None

    @staticmethod
    def _row_to_task(row: sqlite3.Row, status_override: Optional[str] = None) -> Task:
        return Task(
            id=row["id"],
            action=row["action"],
            path=row["path"],
            description=row["description"],
            context_files=json.loads(row["context_files"]),
            priority=row["priority"],
            status=status_override or row["status"],
            result=row["result"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            source=row["source"],
        )
