"""Pending meal session state management."""

import json
import logging
import os
import tempfile
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

TTL_MINUTES = 10


@dataclass
class PendingMealSession:
    user_id: int
    chat_id: int
    raw_text: str
    parsed_meals_json: str
    timestamp: float
    session_key: str = "pending"
    awaiting_disambiguation: list[str] = None

    def __post_init__(self):
        if self.awaiting_disambiguation is None:
            self.awaiting_disambiguation = []


class MealStateStore:
    """Thread-safe store for pending meal sessions."""

    def __init__(self, storage_path: str | None = None):
        self._path = Path(
            storage_path or os.path.join(os.getenv("RECEPTI_DATA_DIR", "data"), "pending_meals.json")
        )
        self._lock = threading.RLock()
        self._sessions: dict[int, dict] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            self._clear_stale()
            if self._path.exists():
                try:
                    with open(self._path, encoding="utf-8") as f:
                        self._sessions = json.load(f)
                except Exception as e:
                    logger.warning(f"Could not load pending meals: {e}")
                    self._sessions = {}
            else:
                self._sessions = {}

    def _atomic_save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(self._path.parent), prefix=".tmp_", text=True
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(self._sessions, f, indent=2, default=str)
                os.fsync(f.fileno())
            os.replace(tmp_path, self._path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def _save(self) -> None:
        with self._lock:
            self._atomic_save()

    def _clear_stale(self) -> None:
        cutoff = time.time() - (TTL_MINUTES * 60)
        stale = [
            uid for uid, sess in self._sessions.items()
            if sess.get("timestamp", 0) < cutoff
        ]
        for uid in stale:
            self._sessions.pop(uid, None)

    def save_pending(self, user_id: int, session: PendingMealSession) -> None:
        with self._lock:
            self._sessions[user_id] = asdict(session)
            self._atomic_save()

    def get_pending(self, user_id: int) -> Optional[PendingMealSession]:
        with self._lock:
            self._clear_stale()
            raw = self._sessions.get(user_id)
            if not raw:
                return None
            if raw.get("timestamp", 0) < time.time() - (TTL_MINUTES * 60):
                self._sessions.pop(user_id, None)
                self._atomic_save()
                return None
            raw["awaiting_disambiguation"] = raw.get("awaiting_disambiguation", [])
            return PendingMealSession(**raw)

    def clear_pending(self, user_id: int) -> None:
        with self._lock:
            self._sessions.pop(user_id, None)
            self._atomic_save()

    def set_disambiguation(self, user_id: int, unmatched_members: list[str]) -> None:
        with self._lock:
            raw = self._sessions.get(user_id)
            if raw:
                raw["awaiting_disambiguation"] = unmatched_members
                self._sessions[user_id] = raw
                self._atomic_save()

    def is_awaiting_disambiguation(self, user_id: int) -> bool:
        with self._lock:
            raw = self._sessions.get(user_id)
            if not raw:
                return False
            return bool(raw.get("awaiting_disambiguation", []))

    def resolve_disambiguation(self, user_id: int, member_name: str) -> bool:
        with self._lock:
            raw = self._sessions.get(user_id)
            if not raw:
                return False
            unmatched = raw.get("awaiting_disambiguation", [])
            if member_name in unmatched:
                unmatched.remove(member_name)
                raw["awaiting_disambiguation"] = unmatched
                self._sessions[user_id] = raw
                self._atomic_save()
                return True
            return False