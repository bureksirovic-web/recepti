"""Recipe storage and search for Recepti."""

import json
from pathlib import Path
from typing import Any

from .models import Recipe, RecipeTags

RECIPES_JSON = "/workspace/repos/Recepti/data/recipes.json"


class RecipeStore:
    """Load/save recipes from recipes.json."""

    def __init__(self, path: str = RECIPES_JSON):
        self._path = path
        self._recipes: list[Recipe] = []
        self._load()

    def _load(self) -> None:
        """Load recipes from JSON file."""
        p = Path(self._path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._recipes = [self._dict_to_recipe(r) for r in data.get("recipes", [])]

    def _save(self) -> None:
        """Persist recipes to JSON file."""
        data = {"recipes": [self._recipe_to_dict(r) for r in self._recipes]}
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _dict_to_recipe(self, d: dict[str, Any]) -> Recipe:
        """Convert dict to Recipe."""
        from .models import Ingredient, NutritionPerServing

        return Recipe(
            id=d["id"],
            name=d["name"],
            description=d.get("description", ""),
            ingredients=[
                Ingredient(i["name"], i["amount"], i["unit"]) for i in d.get("ingredients", [])
            ],
            instructions=d.get("instructions", []),
            tags=RecipeTags(
                cuisine=d.get("tags", {}).get("cuisine", ""),
                meal_type=d.get("tags", {}).get("meal_type", ""),
                dietary_tags=d.get("tags", {}).get("dietary_tags", []),
            ),
            servings=d.get("servings", 1),
            prep_time_min=d.get("prep_time_min", 0),
            cook_time_min=d.get("cook_time_min", 0),
            nutrition_per_serving=NutritionPerServing(
                calories=0.0,
                protein_g=0.0,
                carbs_g=0.0,
                fat_g=0.0,
                fiber_g=0.0,
                iron_mg=0.0,
                calcium_mg=0.0,
                folate_mcg=0.0,
                b12_mcg=0.0,
            ),
            difficulty=d.get("difficulty", "medium"),
            source_url=d.get("source_url", ""),
        )

    def _recipe_to_dict(self, r: Recipe) -> dict[str, Any]:
        """Convert Recipe to dict."""
        return {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "ingredients": [
                {"name": i.name, "amount": i.amount, "unit": i.unit} for i in r.ingredients
            ],
            "instructions": r.instructions,
            "tags": {
                "cuisine": r.tags.cuisine,
                "meal_type": r.tags.meal_type,
                "dietary_tags": r.tags.dietary_tags,
            },
            "servings": r.servings,
            "prep_time_min": r.prep_time_min,
            "cook_time_min": r.cook_time_min,
            "difficulty": r.difficulty,
            "source_url": r.source_url,
        }

    def search_by_ingredients(
        self, available: list[str], exclude: list[str] | None = None
    ) -> list[Recipe]:
        """Return recipes scored by match count (higher = more available)."""
        exclude = exclude or []
        exclude_lower = [e.lower() for e in exclude]
        available_lower = [a.lower() for a in available]
        scored: list[tuple[Recipe, int]] = []
        for recipe in self._recipes:
            # Check exclusions
            ing_names = [i.name.lower() for i in recipe.ingredients]
            if any(e in ing_names for e in exclude_lower):
                continue
            match_count = sum(
                1
                for ing in recipe.ingredients
                if any(s in ing.name.lower() for s in available_lower)
            )
            if match_count > 0:
                scored.append((recipe, match_count))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in scored]

    def search_by_tags(self, tags: dict[str, bool]) -> list[Recipe]:
        """Return recipes matching exact tag booleans."""
        results: list[Recipe] = []
        for recipe in self._recipes:
            match = True
            t = recipe.tags
            for key, val in tags.items():
                if key == "cuisine" and t.cuisine != val:
                    match = False
                elif key == "meal_type" and t.meal_type != val:
                    match = False
                elif key == "dietary_tags" and val not in t.dietary_tags:
                    match = False
            if match:
                results.append(recipe)
        return results

    def get_recipe_by_id(self, recipe_id: int) -> Recipe | None:
        """Return recipe with given id."""
        for r in self._recipes:
            if r.id == recipe_id:
                return r
        return None

    def add_recipe(self, recipe: Recipe) -> int:
        """Add recipe and assign new id if needed."""
        if recipe.id == 0:
            max_id = max((r.id for r in self._recipes), default=0)
            recipe.id = max_id + 1
        self._recipes.append(recipe)
        self._save()
        return recipe.id

    def count(self) -> int:
        """Return number of recipes."""
        return len(self._recipes)
