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
        self._file_mtime: float | None = None

    def _ensure_loaded(self) -> None:
        if self._loaded and self._file_mtime is not None:
            try:
                current_mtime = os.path.getmtime(self._json_path)
                if current_mtime == self._file_mtime:
                    return
            except OSError:
                return
        self._loaded = False
        self._ingredients = {}
        self._file_mtime = None

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
                self._file_mtime = os.path.getmtime(self._json_path)
            except (json.JSONDecodeError, OSError):
                pass
        self._loaded = True

    def get(self, name: str) -> dict | None:
        """Case-insensitive lookup by name or croatian_name. Returns full dict or None."""
        self._ensure_loaded()
        return self._ingredients.get(name.lower())

    def is_available(self, name: str) -> bool:
        entry = self.get(name)
        if entry is None:
            return True
        if entry.get("available") is False:
            return False
        if entry.get("import_required") is True:
            return False
        return True

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
