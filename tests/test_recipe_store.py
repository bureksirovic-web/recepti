"""Tests for RecipeStore."""
from recepti.recipe_store import RecipeStore
from recepti.models import Recipe, Ingredient, RecipeTags, NutritionPerServing


class TestRecipeStore:
    def test_load_empty_file(self, tmp_path):
        recipes_file = tmp_path / "recipes.json"
        recipes_file.write_text('{"recipes": []}')
        store = RecipeStore(str(recipes_file))
        assert store.count() == 0

    def test_load_with_recipes(self, temp_recipes_file):
        store = RecipeStore(str(temp_recipes_file))
        assert store.count() == 7

    def test_get_recipe_by_id(self, temp_recipes_file):
        store = RecipeStore(str(temp_recipes_file))
        recipe = store.get_recipe_by_id(2)
        assert recipe is not None
        assert recipe.name == "Paneer Butter Masala"

    def test_get_recipe_by_id_not_found(self, temp_recipes_file):
        store = RecipeStore(str(temp_recipes_file))
        assert store.get_recipe_by_id(999) is None

    def test_search_by_ingredients(self, temp_recipes_file):
        store = RecipeStore(str(temp_recipes_file))
        results = store.search_by_ingredients(["paneer", "tomatoes"])
        assert len(results) >= 1
        assert results[0].name == "Paneer Butter Masala"

    def test_search_by_ingredients_no_match(self, temp_recipes_file):
        store = RecipeStore(str(temp_recipes_file))
        results = store.search_by_ingredients(["xyz_nonexistent"])
        assert len(results) == 0

    def test_search_by_ingredients_exclude(self, temp_recipes_file):
        store = RecipeStore(str(temp_recipes_file))
        results = store.search_by_ingredients(["rice"], exclude=["masoor_dal"])
        names = [r.name for r in results]
        assert "Curd Rice" in names
        assert "Masoor Dal with Spinach" not in names

    def test_search_by_tags(self, temp_recipes_file):
        store = RecipeStore(str(temp_recipes_file))
        results = store.search_by_tags({"cuisine": "Punjabi"})
        assert len(results) == 2
        assert all(r.tags.cuisine == "Punjabi" for r in results)

    def test_search_by_tags_multiple(self, temp_recipes_file):
        store = RecipeStore(str(temp_recipes_file))
        results = store.search_by_tags({"meal_type": "breakfast"})
        assert len(results) >= 1
        assert all(r.tags.meal_type == "breakfast" for r in results)

    def test_add_recipe(self, temp_recipes_file):
        store = RecipeStore(str(temp_recipes_file))
        new_recipe = Recipe(
            id=0,
            name="Test Recipe",
            description="A test",
            ingredients=[Ingredient("water", 500, "ml")],
            instructions=["Boil water."],
            tags=RecipeTags(cuisine="Fusion", meal_type="lunch", dietary_tags=[]),
            servings=2,
            prep_time_min=5,
            cook_time_min=10,
            nutrition_per_serving=NutritionPerServing(
                calories=0, protein_g=0, carbs_g=0, fat_g=0,
                fiber_g=0, iron_mg=0, calcium_mg=0, folate_mcg=0, b12_mcg=0,
            ),
            difficulty="easy",
        )
        new_id = store.add_recipe(new_recipe)
        assert new_id > 0
        assert store.count() == 8

    def test_dict_roundtrip(self, temp_recipes_file):
        """Verify loaded recipe has correct structure."""
        store = RecipeStore(str(temp_recipes_file))
        recipe = store.get_recipe_by_id(1)
        assert recipe is not None
        assert recipe.id == 1
        assert recipe.name == "Dal Tadka"
        assert len(recipe.ingredients) == 6
        assert recipe.tags.cuisine == "Punjabi"
        assert recipe.difficulty == "easy"