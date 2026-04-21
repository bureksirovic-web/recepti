"""Tests for Croatian recipes data file."""

import json
from pathlib import Path

from recepti.recipe_store import RecipeStore


DATA_DIR = Path(__file__).parent.parent / "data"
CROATIAN_RECIPES_PATH = DATA_DIR / "croatian_recipes.json"
RECIPES_PATH = DATA_DIR / "recipes.json"


class TestCroatianRecipes:
    """Test suite for Croatian recipes data validation."""

    @classmethod
    def setup_class(cls):
        """Load Croatian recipes data once for all tests."""
        with open(CROATIAN_RECIPES_PATH, "r", encoding="utf-8") as f:
            cls.data = json.load(f)

    def test_file_exists(self):
        """Verify croatian_recipes.json file exists."""
        assert CROATIAN_RECIPES_PATH.exists(), "croatian_recipes.json not found"

    def test_recipe_count(self):
        """Verify there are exactly 20 Croatian recipes."""
        recipes = self.data.get("recipes", [])
        assert len(recipes) == 20, f"Expected 20 recipes, found {len(recipes)}"

    def test_ids_unique_and_range(self):
        """Verify all recipe IDs are unique and in range 31-50."""
        ids = [r["id"] for r in self.data.get("recipes", [])]
        assert len(set(ids)) == len(ids), "Duplicate IDs found"
        assert min(ids) == 31, f"Expected min ID 31, got {min(ids)}"
        assert max(ids) == 50, f"Expected max ID 50, got {max(ids)}"

    def test_all_servings_equal_nine(self):
        """Verify all recipes have servings=9."""
        for r in self.data.get("recipes", []):
            assert r.get("servings") == 9, f"Recipe {r['id']} has servings={r.get('servings')}, expected 9"

    def test_cuisine_tag_is_croatian(self):
        """Verify cuisine tag is 'Croatian' for all recipes."""
        for r in self.data.get("recipes", []):
            cuisine = r.get("tags", {}).get("cuisine", "")
            assert cuisine == "Croatian", f"Recipe {r['id']} has cuisine='{cuisine}', expected 'Croatian'"

    def test_ingredient_lists_not_empty(self):
        """Verify all recipes have non-empty ingredient lists."""
        for r in self.data.get("recipes", []):
            ingredients = r.get("ingredients", [])
            assert len(ingredients) > 0, f"Recipe {r['id']} has empty ingredient list"

    def test_no_placeholder_strings(self):
        """Verify no placeholder strings like '充分' in names or descriptions."""
        placeholder = "充分"
        for r in self.data.get("recipes", []):
            name = r.get("name", "")
            desc = r.get("description", "")
            assert placeholder not in name, f"Recipe {r['id']} name contains placeholder '{placeholder}'"
            assert placeholder not in desc, f"Recipe {r['id']} description contains placeholder '{placeholder}'"

    def test_search_by_ingredients_finds_recipe(self):
        """Verify search_by_ingredients finds at least one Croatian recipe."""
        store = RecipeStore(str(CROATIAN_RECIPES_PATH))
        results = store.search_by_ingredients(["potatoes", "onion"])
        assert len(results) >= 1, "search_by_ingredients found no recipes for potatoes + onion"

    def test_extra_sources_merges_croatian_with_main(self):
        """Verify RecipeStore with extra_sources merges Croatian with main recipes."""
        main_store = RecipeStore(str(RECIPES_PATH))
        main_count = main_store.count()

        merged_store = RecipeStore(str(RECIPES_PATH), extra_sources=[str(CROATIAN_RECIPES_PATH)])
        merged_count = merged_store.count()

        assert merged_count == main_count + 20, (
            f"Merged store count ({merged_count}) should equal main ({main_count}) + croatian (20)"
        )
