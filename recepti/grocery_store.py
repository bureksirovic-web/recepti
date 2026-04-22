"""Grocery availability store for Recepti."""

import json
import os


class GroceryStore:
    """Load and serve grocery availability data with singleton pattern."""

    _instance: "GroceryStore | None" = None

    def __new__(cls, json_path: str | None = None) -> "GroceryStore":
        """Return singleton instance, initializing only once."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, json_path: str | None = None):
        """Initialize the store with the path to grocery_availability.json."""
        if self._initialized:
            return
        self._initialized = True

        if json_path is None:
            json_path = os.path.join(
                os.path.dirname(__file__), "..", "data", "grocery_availability.json"
            )
        self._json_path = json_path
        self._ingredients: dict[str, dict] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Lazily load ingredients from JSON file on first access."""
        if self._loaded:
            return
        self._loaded = True

        if os.path.exists(self._json_path):
            try:
                with open(self._json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for entry in data.get("ingredients", []):
                    name_lower = entry.get("name", "").lower()
                    croatian_lower = entry.get("croatian_name", "").lower()
                    if name_lower:
                        self._ingredients[name_lower] = entry
                    if croatian_lower and croatian_lower != name_lower:
                        self._ingredients[croatian_lower] = entry
            except (json.JSONDecodeError, OSError):
                pass

    def get(self, name: str) -> dict | None:
        """Case-insensitive lookup by name or croatian_name. Returns full dict or None."""
        self._ensure_loaded()
        return self._ingredients.get(name.lower())

    def is_available(self, name: str) -> bool:
        """Return True/False via get(). Defaults True if not found."""
        entry = self.get(name)
        if entry is None:
            return True
        return entry.get("available", True)

    def all_ingredients(self) -> list[dict]:
        """Return list of all ingredient dicts."""
        self._ensure_loaded()
        seen: set[int] = set()
        result: list[dict] = []
        for entry in self._ingredients.values():
            entry_id = id(entry)
            if entry_id not in seen:
                seen.add(entry_id)
                result.append(entry)
        return result