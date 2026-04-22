"""Recipe storage and search for Recepti."""

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from .models import Recipe, RecipeTags

RECIPES_JSON = "data/recipes.json"
CROATIAN_RECIPES_JSON = "data/croatian_recipes.json"


class RecipeStore:
    """Load/save recipes from one or more recipe JSON files."""

    def __init__(self, path: str = RECIPES_JSON, extra_sources: list[str] | None = None):
        self._path = path
        self._extra_sources = extra_sources or []
        self._recipes: list[Recipe] = []
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        with self._lock:
            all_files: list[str] = []
            if Path(self._path).exists():
                all_files.append(self._path)
            for src in self._extra_sources:
                if Path(src).exists():
                    all_files.append(src)
            recipes: list[Recipe] = []
            for file_path in all_files:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                recipes.extend(self._dict_to_recipe(r) for r in data.get("recipes", []))
            self._recipes = recipes

    def _save(self) -> None:
        with self._lock:
            data = {"recipes": [self._recipe_to_dict(r) for r in self._recipes]}
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=os.path.dirname(os.path.abspath(self._path)), prefix=".recipes.tmp."
            )
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                os.fsync(f.fileno())
            os.replace(tmp_path, self._path)

    def _dict_to_recipe(self, d: dict[str, Any]) -> Recipe:
        """Convert dict to Recipe."""
        from .models import Ingredient, NutritionPerServing

        n = d.get("nutrition_per_serving", {})
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
                calories=float(n.get("calories", 0)),
                protein_g=float(n.get("protein_g", 0)),
                carbs_g=float(n.get("carbs_g", 0)),
                fat_g=float(n.get("fat_g", 0)),
                fiber_g=float(n.get("fiber_g", 0)),
                iron_mg=float(n.get("iron_mg", 0)),
                calcium_mg=float(n.get("calcium_mg", 0)),
                folate_mcg=float(n.get("folate_mcg", 0)),
                b12_mcg=float(n.get("b12_mcg", 0)),
            ),
            difficulty=d.get("difficulty", "medium"),
            source_url=d.get("source_url", ""),
        )

    def _recipe_to_dict(self, r: Recipe) -> dict[str, Any]:
        """Convert Recipe to dict."""
        n = r.nutrition_per_serving
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
            "nutrition_per_serving": {
                "calories": n.calories,
                "protein_g": n.protein_g,
                "carbs_g": n.carbs_g,
                "fat_g": n.fat_g,
                "fiber_g": n.fiber_g,
                "iron_mg": n.iron_mg,
                "calcium_mg": n.calcium_mg,
                "folate_mcg": n.folate_mcg,
                "b12_mcg": n.b12_mcg,
            },
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

    def find_by_name(self, query: str) -> list[Recipe]:
        """Return recipes whose name contains query (case-insensitive, partial match)."""
        q = query.lower()
        scored: list[tuple[Recipe, int]] = []
        for recipe in self._recipes:
            score = 0
            name_lower = recipe.name.lower()
            if name_lower == q:
                score = 100
            elif name_lower.startswith(q):
                score = 80
            elif q in name_lower:
                score = name_lower.find(q) + 1
            if score > 0:
                scored.append((recipe, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in scored]

    def add_recipe(self, recipe: Recipe) -> int:
        """Add recipe and assign new id if needed."""
        with self._lock:
            if recipe.id == 0:
                max_id = max((r.id for r in self._recipes), default=0)
                recipe.id = max_id + 1
            self._recipes.append(recipe)
            self._save()
            return recipe.id

    def count(self) -> int:
        """Return number of recipes."""
        return len(self._recipes)
