"""Undo journal — logs every file modification for rollback.

Each change is stored as a timestamped backup of the original file
(or a marker for newly created files) so any Coder action can be reversed.
"""

import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from orchestra.config import get_undo_dir


@dataclass
class UndoEntry:
    timestamp: float
    task_id: int
    action: str
    target_path: str
    backup_path: Optional[str]  # None if file was newly created
    description: str


class UndoJournal:
    """Records file operations for rollback capability."""

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._undo_dir = get_undo_dir(project_root)
        self._log_path = self._undo_dir / "journal.jsonl"

    def record_before_write(self, task_id: int, target: Path, action: str, description: str) -> None:
        """Snapshot the target file before the Coder modifies it."""
        backup_path: Optional[str] = None

        if target.exists():
            # Save a backup of the original
            ts = int(time.time() * 1000)
            backup_name = f"{ts}_{task_id}_{target.name}"
            backup_dest = self._undo_dir / backup_name
            shutil.copy2(target, backup_dest)
            backup_path = str(backup_dest)

        entry = UndoEntry(
            timestamp=time.time(),
            task_id=task_id,
            action=action,
            target_path=str(target),
            backup_path=backup_path,
            description=description,
        )

        with open(self._log_path, "a") as f:
            f.write(json.dumps(entry.__dict__) + "\n")

    def undo_last(self) -> Optional[str]:
        """Undo the most recent change. Returns a description of what was undone."""
        if not self._log_path.exists():
            return None

        lines = self._log_path.read_text().strip().split("\n")
        if not lines:
            return None

        last = json.loads(lines[-1])
        entry = UndoEntry(**last)

        target = Path(entry.target_path)

        if entry.backup_path:
            # Restore the backup
            shutil.copy2(entry.backup_path, target)
            msg = f"Restored {target.name} from backup"
        else:
            # File was newly created — delete it
            if target.exists():
                target.unlink()
            msg = f"Removed {target.name} (was newly created)"

        # Remove the last line from the journal
        remaining = lines[:-1]
        self._log_path.write_text("\n".join(remaining) + "\n" if remaining else "")

        return msg

    def get_recent(self, limit: int = 10) -> list[UndoEntry]:
        """Return recent undo entries."""
        if not self._log_path.exists():
            return []

        lines = self._log_path.read_text().strip().split("\n")
        entries = []
        for line in reversed(lines[-limit:]):
            if line.strip():
                entries.append(UndoEntry(**json.loads(line)))
        return entries
