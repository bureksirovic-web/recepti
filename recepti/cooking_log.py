"""Persistent cooking log — tracks what the family cooked and who ate what."""

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from recepti.models import CookingSession, FamilyMember

logger = logging.getLogger(__name__)


class CookingLogStore:
    """Loads/saves the family cooking log from a JSON file."""

    def __init__(self, log_path: str, members_path: str):
        self.log_path = Path(log_path)
        self.members_path = Path(members_path)
        self._sessions: list[CookingSession] = []
        self._members: dict[int, FamilyMember] = {}
        self._next_session_id: int = 1
        self._load()

    # ── Members ─────────────────────────────────────────────────────

    def _load_members(self) -> None:
        if not self.members_path.exists():
            return
        try:
            with open(self.members_path) as f:
                data = json.load(f)
            for d in data if isinstance(data, list) else []:
                self._members[d["id"]] = FamilyMember(
                    id=d["id"],
                    name=d["name"],
                    sex=d["sex"],
                    age_years=float(d["age_years"]),
                    pregnant=d.get("pregnant", False),
                    lactating=d.get("lactating", False),
                    dislikes=d.get("dislikes", []),
                )
        except Exception as e:
            logger.warning(f"Could not load members from {self.members_path}: {e}")

    def get_members(self) -> list[FamilyMember]:
        return list(self._members.values())

    def get_member(self, member_id: int) -> Optional[FamilyMember]:
        return self._members.get(member_id)

    def add_member(self, member: FamilyMember) -> None:
        self._members[member.id] = member
        self._save_members()

    def remove_member(self, member_id: int) -> None:
        self._members.pop(member_id, None)
        self._save_members()

    def _save_members(self) -> None:
        data = [
            {
                "id": m.id,
                "name": m.name,
                "sex": m.sex,
                "age_years": m.age_years,
                "pregnant": m.pregnant,
                "lactating": m.lactating,
                "dislikes": m.dislikes,
            }
            for m in self._members.values()
        ]
        self.members_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.members_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    # ── Sessions ───────────────────────────────────────────────────────

    def _load(self) -> None:
        self._load_members()
        if not self.log_path.exists():
            self._sessions = []
            self._next_session_id = 1
            return
        try:
            with open(self.log_path) as f:
                data = json.load(f)
            self._sessions = [
                CookingSession(
                    id=s["id"],
                    date=date.fromisoformat(s["date"]),
                    recipe_id=s["recipe_id"],
                    servings_made=float(s["servings_made"]),
                    servings_served={
                        int(k): float(v) for k, v in s.get("servings_served", {}).items()
                    },
                    notes=s.get("notes", ""),
                )
                for s in data if isinstance(data, list)
            ]
            self._next_session_id = max(s.id for s in self._sessions) + 1 if self._sessions else 1
        except Exception as e:
            logger.warning(f"Could not load cooking log: {e}")
            self._sessions = []
            self._next_session_id = 1

    def _save(self) -> None:
        data = [
            {
                "id": s.id,
                "date": s.date.isoformat(),
                "recipe_id": s.recipe_id,
                "servings_made": s.servings_made,
                "servings_served": {str(k): v for k, v in s.servings_served.items()},
                "notes": s.notes,
            }
            for s in self._sessions
        ]
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def log_session(
        self,
        recipe_id: int,
        servings_made: float,
        servings_served: Optional[dict[int, float]] = None,
        notes: str = "",
        log_date: Optional[date] = None,
    ) -> CookingSession:
        session = CookingSession(
            id=self._next_session_id,
            date=log_date or date.today(),
            recipe_id=recipe_id,
            servings_made=servings_made,
            servings_served=servings_served or {},
            notes=notes,
        )
        self._sessions.append(session)
        self._next_session_id += 1
        self._save()
        return session

    def get_sessions(
        self,
        recipe_id: Optional[int] = None,
        since: Optional[date] = None,
        member_id: Optional[int] = None,
    ) -> list[CookingSession]:
        results = self._sessions
        if recipe_id is not None:
            results = [s for s in results if s.recipe_id == recipe_id]
        if since is not None:
            results = [s for s in results if s.date >= since]
        if member_id is not None:
            results = [s for s in results if member_id in s.servings_served]
        return sorted(results, key=lambda s: s.date, reverse=True)

    def get_recent_sessions(self, days: int = 7) -> list[CookingSession]:
        cutoff = date.today() - timedelta(days=days)
        return [s for s in self._sessions if s.date >= cutoff]

    def total_servings_for_member(self, member_id: int, recipe_id: int) -> float:
        return sum(
            s.servings_served.get(member_id, 0)
            for s in self._sessions
            if s.recipe_id == recipe_id
        )

    def remove_last_session(self) -> bool:
        if not self._sessions:
            return False
        self._sessions.pop()
        self._next_session_id = max(s.id for s in self._sessions) + 1 if self._sessions else 1
        self._save()
        return True