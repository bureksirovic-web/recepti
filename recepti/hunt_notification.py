"""Persistent notification store for recipe hunter discoveries."""

import json
import logging
import os
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class HuntNotification:
    id: int
    timestamp: str
    recipes_found: int
    recipes_added: int
    cuisines_blacklisted: list[str]
    hunt_summary: str
    recipes: list[str]


class HuntNotificationStore:
    """Persistent notification queue for recipe hunter discoveries."""

    def __init__(self, path: str):
        self.path = Path(path)
        self._notifications: list[HuntNotification] = []
        self._next_id: int = 1
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self.path.exists():
                self._notifications = []
                self._next_id = 1
                return
            try:
                with open(self.path) as f:
                    data = json.load(f)
                self._notifications = [
                    HuntNotification(
                        id=n["id"],
                        timestamp=n["timestamp"],
                        recipes_found=n["recipes_found"],
                        recipes_added=n["recipes_added"],
                        cuisines_blacklisted=n.get("cuisines_blacklisted", []),
                        hunt_summary=n.get("hunt_summary", ""),
                        recipes=n.get("recipes", []),
                    )
                    for n in data if isinstance(data, list)
                ]
                self._next_id = (
                    max(n.id for n in self._notifications) + 1
                    if self._notifications
                    else 1
                )
            except Exception as e:
                logger.warning(f"Could not load hunt notifications: {e}")
                self._notifications = []
                self._next_id = 1

    def _atomic_save(self, data: list) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=".hunt_notifications.tmp."
        )
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(data, f, indent=2, default=str)
            os.fsync(f.fileno())
        os.replace(tmp_path, self.path)

    def _save(self) -> None:
        with self._lock:
            data = [
                {
                    "id": n.id,
                    "timestamp": n.timestamp,
                    "recipes_found": n.recipes_found,
                    "recipes_added": n.recipes_added,
                    "cuisines_blacklisted": n.cuisines_blacklisted,
                    "hunt_summary": n.hunt_summary,
                    "recipes": n.recipes,
                }
                for n in self._notifications
            ]
            self._atomic_save(data)

    def enqueue(
        self,
        recipes_found: int,
        recipes_added: int,
        cuisines_blacklisted: list[str],
        recipes: list[str],
    ) -> HuntNotification:
        with self._lock:
            notification = HuntNotification(
                id=self._next_id,
                timestamp=datetime.now().isoformat(),
                recipes_found=recipes_found,
                recipes_added=recipes_added,
                cuisines_blacklisted=cuisines_blacklisted,
                hunt_summary=self._generate_summary(recipes_added, cuisines_blacklisted),
                recipes=recipes,
            )
            self._notifications.append(notification)
            self._next_id += 1
            self._save()
            return notification

    def _generate_summary(self, recipes_added: int, cuisines_blacklisted: list[str]) -> str:
        parts: list[str] = []
        if recipes_added > 0:
            parts.append(f"Hunter added {recipes_added} recipe{'s' if recipes_added != 1 else ''}")
        if cuisines_blacklisted:
            parts.append(f"blacklisted cuisine{'s' if len(cuisines_blacklisted) != 1 else ''}: {', '.join(cuisines_blacklisted)}")
        return ", ".join(parts) if parts else "Hunter completed a scan"

    def get_pending(self) -> list[HuntNotification]:
        with self._lock:
            return list(self._notifications)

    def clear_pending(self) -> None:
        with self._lock:
            self._notifications = []
            self._save()

    def get_recent(self, limit: int = 10) -> list[HuntNotification]:
        with self._lock:
            sorted_notifications = sorted(
                self._notifications, key=lambda n: n.timestamp, reverse=True
            )
            return sorted_notifications[:limit]