"""Kid meal tracking for Recepti."""

import json
import os
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .models import Recipe


class KidMealHistory:
    """Track a child's meal history and preferences."""

    def __init__(self, storage_path: str | None = None):
        self._storage_path = (
            storage_path
            or os.path.join(os.getenv("RECEPTI_DATA_DIR", "data"), "kid_history.json")
        )
        self._data: dict[int, dict[str, Any]] = {}
        self._recipe_store: Recipe | None = None
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        """Load history from disk."""
        with self._lock:
            path = Path(self._storage_path)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                # JSON deserializes dict keys as strings; convert back to int child_ids
                self._data = {int(k): v for k, v in raw.items()}
            else:
                self._data = {}

    def _save(self) -> None:
        """Persist history to disk atomically."""
        with self._lock:
            path = Path(self._storage_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", text=True)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, path)
            except Exception:
                if os.path.exists(tmp):
                    os.unlink(tmp)
                raise

    def _ensure_child(self, child_id: int) -> None:
        """Ensure child entry exists."""
        if child_id not in self._data:
            self._data[child_id] = {"history": [], "favorites_cache": [], "dislikes_cache": []}

    def _set_recipe_store(self, store: Recipe) -> None:
        """Set the recipe store for name lookups."""
        with self._lock:
            self._recipe_store = store

    def record_meal(
        self,
        child_id: int,
        recipe_id: int,
        meal_type: str,
        date: str,
        amount_eaten: float,
        notes: str = "",
    ) -> None:
        """Append a meal record to history."""
        with self._lock:
            self._ensure_child(child_id)
            entry = {
                "recipe_id": recipe_id,
                "meal_type": meal_type,
                "date": date,
                "amount_eaten": amount_eaten,
                "notes": notes,
            }
            self._data[child_id]["history"].append(entry)
            # Invalidate caches
            self._data[child_id]["favorites_cache"] = []
            self._data[child_id]["dislikes_cache"] = []
            self._save()

    def get_child_history(self, child_id: int, days: int = 30) -> list[dict[str, Any]]:
        """Get recent history for a child, enriched with recipe names."""
        with self._lock:
            if child_id not in self._data:
                return []
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff.strftime("%Y-%m-%d")
            result = []
            for entry in self._data[child_id]["history"]:
                if entry["date"] >= cutoff_str:
                    recipe_name = ""
                    if self._recipe_store:
                        r = self._recipe_store.get_recipe_by_id(entry["recipe_id"])
                        if r:
                            recipe_name = r.name
                    result.append(
                        {
                            "date": entry["date"],
                            "meal_type": entry["meal_type"],
                            "recipe_name": recipe_name,
                            "amount_eaten": entry["amount_eaten"],
                            "notes": entry["notes"],
                        }
                    )
            return result

    def _aggregate_by_recipe(self, entries: list[dict]) -> dict[int, float]:
        """Aggregate entries by recipe_id, returning {recipe_id: total_eaten}."""
        totals: dict[int, float] = {}
        for e in entries:
            rid = e["recipe_id"]
            totals[rid] = totals.get(rid, 0) + e["amount_eaten"]
        return totals

    def get_child_favorites(self, child_id: int, limit: int = 5) -> list[int]:
        """Return recipe_ids ranked by amount_eaten."""
        with self._lock:
            if child_id not in self._data:
                return []
            entries = self._data[child_id]["history"]
            if not entries:
                return []
            totals = self._aggregate_by_recipe(entries)
            ranked = sorted(totals, key=lambda r: totals[r], reverse=True)
            return ranked[:limit]

    def get_child_dislikes(self, child_id: int) -> list[str]:
        """Return ingredient names from history where amount_eaten < 0.3."""
        with self._lock:
            if child_id not in self._data:
                return []
            disliked: set[str] = set()
            for entry in self._data[child_id]["history"]:
                if entry["amount_eaten"] < 0.3 and self._recipe_store:
                    r = self._recipe_store.get_recipe_by_id(entry["recipe_id"])
                    if r:
                        for ing in r.ingredients:
                            disliked.add(ing.name)
            return list(disliked)

    def get_family_summary(self, days: int = 7) -> dict[str, dict[str, Any]]:
        """Return summary per child: meals_eaten, most_eaten_recipes, dislikes."""
        with self._lock:
            summary: dict[str, dict[str, Any]] = {}
            for child_id, data in self._data.items():
                cutoff = datetime.now() - timedelta(days=days)
                cutoff_str = cutoff.strftime("%Y-%m-%d")
                recent = [e for e in data["history"] if e["date"] >= cutoff_str]
                meals_eaten = len(recent)
                totals = self._aggregate_by_recipe(recent)
                top_recipes = sorted(totals, key=lambda r: totals[r], reverse=True)[:5]
                most_eaten_names = []
                if self._recipe_store:
                    for rid in top_recipes:
                        r = self._recipe_store.get_recipe_by_id(rid)
                        if r:
                            most_eaten_names.append(r.name)
                # dislikes (amount_eaten < 0.3)
                dislikes: set[str] = set()
                for e in recent:
                    if e["amount_eaten"] < 0.3 and self._recipe_store:
                        r = self._recipe_store.get_recipe_by_id(e["recipe_id"])
                        if r:
                            for ing in r.ingredients:
                                dislikes.add(ing.name)
                summary[str(child_id)] = {
                    "meals_eaten": meals_eaten,
                    "most_eaten_recipes": most_eaten_names,
                    "dislikes": list(dislikes),
                }
            return summary
