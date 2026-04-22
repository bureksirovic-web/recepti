"""Background recipe pre-loader for periodic expansion."""

import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class LastExpansion:
    """Record of last expansion run."""
    last_run: str  # ISO format
    ingredient: str
    recipes_added: int


class RecipePreloader:
    """
    Background pre-loader for recipe expansion.
    Selects random ingredients from Croatia whitelist and expands the DB.
    """

    def __init__(
        self,
        croatia_ingredients_path: str = "data/croatia_ingredients.json",
        last_expansion_path: str = "data/last_expansion.json",
    ):
        self.croatia_ingredients_path = croatia_ingredients_path
        self.last_expansion_path = last_expansion_path
        self._all_ingredients: list[str] = []
        self._load_ingredients()

    def _load_ingredients(self) -> None:
        """Load all Croatia ingredients into a flat list."""
        try:
            with open(self.croatia_ingredients_path, encoding="utf-8") as f:
                data = json.load(f)
            self._all_ingredients = []
            for category, ingredients in data.get("categories", {}).items():
                self._all_ingredients.extend(ingredients)
            logger.info(
                f"RecipePreloader loaded {len(self._all_ingredients)} ingredients"
            )
        except Exception as e:
            logger.warning(f"Could not load ingredients: {e}")
            self._all_ingredients = [
                "lentils", "chickpeas", "mushrooms", "spinach",
                "potatoes", "tomatoes", "rice", "pasta"
            ]

    def _should_run_today(self) -> bool:
        """Return True if daily expansion should run (once per 24h)."""
        try:
            with open(self.last_expansion_path, encoding="utf-8") as f:
                data = json.load(f)
            last_run = datetime.fromisoformat(data["last_run"])
            hours_since = (datetime.now() - last_run).total_seconds() / 3600
            return hours_since >= 24
        except (FileNotFoundError, KeyError, ValueError):
            return True

    def _save_last_run(
        self, ingredient: str, recipes_added: int
    ) -> None:
        """Save the last expansion run record."""
        with open(self.last_expansion_path, "w", encoding="utf-8") as f:
            json.dump({
                "last_run": datetime.now().isoformat(),
                "ingredient": ingredient,
                "recipes_added": recipes_added,
            }, f, indent=2)

    def _pick_random_ingredient(self) -> str:
        """Pick a random ingredient, preferring legumes and vegetables."""
        priority_ingredients = [
            ing for ing in self._all_ingredients
            if ing in [
                "lentils", "red lentils", "green lentils", "chickpeas",
                "white beans", "mushrooms", "spinach", "zucchini",
                "cauliflower", "eggplant", "bell pepper"
            ]
        ]
        pool = priority_ingredients if priority_ingredients else self._all_ingredients
        return random.choice(pool)

    def get_last_expansion(self) -> Optional[LastExpansion]:
        """Return the last expansion record, or None."""
        try:
            with open(self.last_expansion_path, encoding="utf-8") as f:
                data = json.load(f)
            return LastExpansion(
                last_run=data["last_run"],
                ingredient=data["ingredient"],
                recipes_added=data["recipes_added"],
            )
        except (FileNotFoundError, KeyError, ValueError):
            return None

    def run_daily(self, expander: "RecipeExpander") -> bool:
        """
        Run daily background expansion.

        Args:
            expander: RecipeExpander instance

        Returns:
            True if expansion ran, False if skipped (already ran today)
        """
        if not self._should_run_today():
            logger.info("Daily expansion skipped — already ran today")
            return False

        ingredient = self._pick_random_ingredient()
        logger.info(f"Daily expansion: '{ingredient}'")

        results = expander.expand_ingredient(ingredient, max_recipes=2)
        success_count = sum(1 for r in results if r.success)

        self._save_last_run(ingredient, success_count)

        logger.info(
            f"Daily expansion done: {success_count} recipes added "
            f"for '{ingredient}'"
        )
        return True