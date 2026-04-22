"""Tests for RecipeExpander."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from recepti.models import Ingredient, NutritionPerServing, Recipe, RecipeTags
from recepti.recipe_expander import ExpansionResult, RecipeExpander
from recepti.recipe_store import RecipeStore


@pytest.fixture
def temp_data_dir(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    croatia_file = data_dir / "croatia_ingredients.json"
    croatia_file.write_text(json.dumps({
        "categories": {
            "vegetables": ["onion", "tomato", "potato", "garlic", "spinach"],
            "legumes": ["lentils", "chickpeas"],
            "dairy": ["milk", "yogurt", "eggs", "cheese"],
            "grains": ["rice", "flour", "bread"],
            "pantry": ["olive oil", "salt", "pepper", "sugar", "stock cubes"],
        }
    }))
    expanded_file = data_dir / "expanded_recipes.json"
    expanded_file.write_text(json.dumps({"recipes": [], "version": 1}))
    return data_dir


@pytest.fixture
def empty_store(tmp_path):
    recipes_file = tmp_path / "recipes.json"
    recipes_file.write_text('{"recipes": []}')
    return RecipeStore(str(recipes_file))


@pytest.fixture
def store_with_recipe(tmp_path):
    recipes_file = tmp_path / "recipes.json"
    recipes_file.write_text(json.dumps({
        "recipes": [{
            "id": 1,
            "name": "Spinach Dal",
            "description": "Simple lentil dish",
            "ingredients": [{"name": "lentils", "amount": "200", "unit": "g"}],
            "instructions": ["Cook lentils", "Add spinach"],
            "tags": {"cuisine": "Indian", "meal_type": "lunch", "dietary_tags": ["vegetarian"]},
            "servings": 4,
            "prep_time_min": 10,
            "cook_time_min": 20,
            "difficulty": "easy",
        }]
    }))
    return RecipeStore(str(recipes_file))


@pytest.fixture
def sample_recipe_response():
    return Recipe(
        id=0,
        name="Lentil Soup",
        description="A warming Croatian lentil soup",
        ingredients=[
            Ingredient("lentils", "200", "g"),
            Ingredient("onion", "1", "medium"),
            Ingredient("carrot", "2", "medium"),
        ],
        instructions=["Sauté onion and carrot", "Add lentils and stock", "Simmer 30 minutes"],
        tags=RecipeTags(cuisine="Croatian", meal_type="lunch", dietary_tags=["vegetarian"]),
        servings=4,
        prep_time_min=15,
        cook_time_min=30,
        nutrition_per_serving=NutritionPerServing(0, 0, 0, 0, 0, 0, 0, 0, 0),
        difficulty="easy",
        source_url="https://example.com/lentil-soup",
    )


class TestRecipeExpanderUnit:

    def test_expand_ingredient_returns_empty_when_no_web_results(self, temp_data_dir, empty_store):
        expander = RecipeExpander(
            store=empty_store,
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            expanded_recipes_path=str(temp_data_dir / "expanded_recipes.json"),
        )

        with patch("recepti.recipe_expander.DDGS") as mock_ddgs_class:
            mock_ddgs = MagicMock()
            mock_ddgs.text.return_value = []
            mock_ddgs_class.return_value.__enter__ = MagicMock(return_value=mock_ddgs)
            mock_ddgs_class.return_value.__exit__ = MagicMock(return_value=False)

            results = expander.expand_ingredient("nonexistent_ingredient_xyz")

            # Should return empty list since no URLs found
            assert results == []

    def test_expand_ingredient_handles_ddgs_error(self, temp_data_dir, empty_store):
        expander = RecipeExpander(
            store=empty_store,
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            expanded_recipes_path=str(temp_data_dir / "expanded_recipes.json"),
        )

        with patch("recepti.recipe_expander.DDGS") as mock_ddgs_class:
            mock_ddgs = MagicMock()
            mock_ddgs.text.side_effect = Exception("Network error")
            mock_ddgs_class.return_value.__enter__ = MagicMock(return_value=mock_ddgs)
            mock_ddgs_class.return_value.__exit__ = MagicMock(return_value=False)

            results = expander.expand_ingredient("lentils")

            # Should return empty list since search failed
            assert results == []

    def test_expand_ingredient_skips_duplicate_recipes(self, temp_data_dir, store_with_recipe, sample_recipe_response):
        expander = RecipeExpander(
            store=store_with_recipe,
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            expanded_recipes_path=str(temp_data_dir / "expanded_recipes.json"),
        )

        # Mock DDGS to return a URL
        with patch("recepti.recipe_expander.DDGS") as mock_ddgs_class:
            mock_ddgs = MagicMock()
            mock_ddgs.text.return_value = iter([{"href": "https://example.com/spinach-dal"}])
            mock_ddgs_class.return_value.__enter__ = MagicMock(return_value=mock_ddgs)
            mock_ddgs_class.return_value.__exit__ = MagicMock(return_value=False)

            # Create duplicate recipe (similar name to "Spinach Dal" in store)
            duplicate_response = Recipe(
                id=0,
                name="Spinach Dal with Garlic",  # Similar name, should be detected as duplicate
                description="Another spinach dal",
                ingredients=[Ingredient("spinach", "100", "g"), Ingredient("lentils", "200", "g")],
                instructions=["Cook spinach dal"],
                tags=RecipeTags(cuisine="Indian", meal_type="lunch", dietary_tags=["vegetarian"]),
                servings=4,
                prep_time_min=10,
                cook_time_min=20,
                nutrition_per_serving=NutritionPerServing(0, 0, 0, 0, 0, 0, 0, 0, 0),
                difficulty="easy",
                source_url="https://example.com/spinach-dal",
            )

            with patch("recepti.llm_service.extract_recipe_from_url", return_value=duplicate_response):
                with patch.object(expander, "_fetch_page_content", return_value="dummy content"):
                    results = expander.expand_ingredient("spinach")

                    # Should have one result marked as duplicate
                    assert len(results) == 1
                    assert results[0].was_duplicate is True
                    assert results[0].success is False

    def test_expand_ingredient_saves_recipe_on_success(self, temp_data_dir, empty_store, sample_recipe_response, tmp_path):
        expander = RecipeExpander(
            store=empty_store,
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            expanded_recipes_path=str(temp_data_dir / "expanded_recipes.json"),
        )

        with patch("recepti.recipe_expander.DDGS") as mock_ddgs_class:
            mock_ddgs = MagicMock()
            mock_ddgs.text.return_value = iter([{"href": "https://example.com/lentil-soup"}])
            mock_ddgs_class.return_value.__enter__ = MagicMock(return_value=mock_ddgs)
            mock_ddgs_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("recepti.llm_service.extract_recipe_from_url", return_value=sample_recipe_response):
                with patch.object(expander, "_fetch_page_content", return_value="dummy content"):
                    results = expander.expand_ingredient("lentils")

                    # Should have one success result
                    assert len(results) == 1
                    assert results[0].success is True
                    assert results[0].recipe is not None
                    assert results[0].recipe.name == "Lentil Soup"

                    # Verify recipe was saved to expanded_recipes.json
                    expanded_path = temp_data_dir / "expanded_recipes.json"
                    saved_data = json.loads(expanded_path.read_text())
                    assert len(saved_data["recipes"]) == 1
                    assert saved_data["recipes"][0]["name"] == "Lentil Soup"

    def test_expand_single_recipe_handles_fetch_failure(self, temp_data_dir, empty_store):
        expander = RecipeExpander(
            store=empty_store,
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            expanded_recipes_path=str(temp_data_dir / "expanded_recipes.json"),
        )

        with patch("recepti.llm_service.extract_recipe_from_url") as mock_extract:
            mock_extract.return_value = None

            result = expander.expand_single_recipe("https://example.com/recipe", "Use Croatia ingredients")

            assert result.success is False
            assert "fetch" in result.error_message.lower() or "Failed" in result.error_message

    def test_expand_single_recipe_handles_llm_extraction_failure(self, temp_data_dir, empty_store):
        expander = RecipeExpander(
            store=empty_store,
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            expanded_recipes_path=str(temp_data_dir / "expanded_recipes.json"),
        )

        with patch.object(expander, "_fetch_page_content", return_value="page content here"):
            with patch("recepti.llm_service.extract_recipe_from_url", return_value=None):
                result = expander.expand_single_recipe("https://example.com/recipe", "Use Croatia ingredients")

                assert result.success is False
                assert "LLM" in result.error_message or "extraction" in result.error_message.lower()

    def test_expand_single_recipe_rejects_non_vegetarian(self, temp_data_dir, empty_store):
        expander = RecipeExpander(
            store=empty_store,
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            expanded_recipes_path=str(temp_data_dir / "expanded_recipes.json"),
        )

        non_veg_recipe = Recipe(
            id=0,
            name="Chicken Curry",
            description="Chicken curry recipe",
            ingredients=[Ingredient("chicken", "500", "g"), Ingredient("onion", "2", "medium")],
            instructions=["Cook chicken curry"],
            tags=RecipeTags(cuisine="Indian", meal_type="lunch", dietary_tags=[]),
            servings=4,
            prep_time_min=15,
            cook_time_min=30,
            nutrition_per_serving=NutritionPerServing(0, 0, 0, 0, 0, 0, 0, 0, 0),
            difficulty="medium",
            source_url="https://example.com/chicken-curry",
        )

        with patch.object(expander, "_fetch_page_content", return_value="page content"):
            with patch("recepti.llm_service.extract_recipe_from_url", return_value=non_veg_recipe):
                result = expander.expand_single_recipe("https://example.com/recipe", "Use Croatia ingredients")

                assert result.success is False
                assert "non-vegetarian" in result.error_message.lower() or "vegetarian" in result.error_message.lower()

    def test_normalize_name(self, temp_data_dir, empty_store):
        expander = RecipeExpander(
            store=empty_store,
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            expanded_recipes_path=str(temp_data_dir / "expanded_recipes.json"),
        )

        assert expander._normalize_name("  Lentil Soup!  ") == "lentil soup"
        assert expander._normalize_name("Spinach Dal With Garlic") == "spinach dal with garlic"
        assert expander._normalize_name("  Simple   Recipe  ") == "simple recipe"

    def test_is_strictly_vegetarian(self, temp_data_dir, empty_store):
        expander = RecipeExpander(
            store=empty_store,
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            expanded_recipes_path=str(temp_data_dir / "expanded_recipes.json"),
        )

        # Should return True for vegetarian ingredients
        veg_ingredients = ["lentils", "rice", "onion", "tomato"]
        veg_instructions = ["Cook lentils", "Add rice"]
        assert expander._is_strictly_vegetarian(veg_ingredients, veg_instructions) is True

        # Should return False for meat
        assert expander._is_strictly_vegetarian(["chicken", "rice"], veg_instructions) is False

        # Should return False for fish
        assert expander._is_strictly_vegetarian(veg_ingredients, ["Add salmon"]) is False

        # Should return False for tofu (meat substitute)
        assert expander._is_strictly_vegetarian(veg_ingredients + ["tofu"], veg_instructions) is False

    def test_is_duplicate(self, temp_data_dir, store_with_recipe):
        expander = RecipeExpander(
            store=store_with_recipe,
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            expanded_recipes_path=str(temp_data_dir / "expanded_recipes.json"),
        )

        # Should detect duplicate (similar words)
        assert expander._is_duplicate("Spinach Dal Special") is True

        # Should not detect duplicate (different words)
        assert expander._is_duplicate("Chocolate Cake") is False

        # Single word names should not be flagged as duplicate
        assert expander._is_duplicate("Lentils") is False

    def test_recipe_with_missing_optional_fields_handled(self, temp_data_dir, empty_store):
        expander = RecipeExpander(
            store=empty_store,
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            expanded_recipes_path=str(temp_data_dir / "expanded_recipes.json"),
        )

        # Recipe with minimal fields (no source_url, etc.)
        minimal_recipe = Recipe(
            id=0,
            name="Simple Rice",
            description="",
            ingredients=[Ingredient("rice", "1", "cup")],
            instructions=["Cook rice"],
            tags=RecipeTags(cuisine="", meal_type="lunch", dietary_tags=["vegetarian"]),
            servings=2,
            prep_time_min=5,
            cook_time_min=15,
            nutrition_per_serving=NutritionPerServing(0, 0, 0, 0, 0, 0, 0, 0, 0),
            difficulty="easy",
            source_url="",  # Missing source URL
        )

        with patch("recepti.recipe_expander.DDGS") as mock_ddgs_class:
            mock_ddgs = MagicMock()
            mock_ddgs.text.return_value = iter([{"href": "https://example.com/simple-rice"}])
            mock_ddgs_class.return_value.__enter__ = MagicMock(return_value=mock_ddgs)
            mock_ddgs_class.return_value.__exit__ = MagicMock(return_value=False)

            with patch("recepti.llm_service.extract_recipe_from_url", return_value=minimal_recipe):
                with patch.object(expander, "_fetch_page_content", return_value="page content"):
                    results = expander.expand_ingredient("rice")

                    # Should succeed despite missing optional fields
                    assert len(results) == 1
                    assert results[0].success is True
                    assert results[0].recipe.name == "Simple Rice"

    def test_check_ingredient_availability(self, temp_data_dir, empty_store):
        expander = RecipeExpander(
            store=empty_store,
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            expanded_recipes_path=str(temp_data_dir / "expanded_recipes.json"),
        )

        ingredients = ["onion", "chicken", "rice", "tofu", "garlic"]
        available, unavailable = expander._check_ingredient_availability(ingredients)

        assert "onion" in available
        assert "rice" in available
        assert "garlic" in available
        assert "chicken" in unavailable
        assert "tofu" in unavailable


class TestExpansionResult:

    def test_expansion_result_success(self):
        recipe = Recipe(
            id=1,
            name="Test Recipe",
            description="Test",
            ingredients=[],
            instructions=[],
            tags=RecipeTags(cuisine="Test", meal_type="lunch", dietary_tags=[]),
            servings=2,
            prep_time_min=10,
            cook_time_min=20,
            nutrition_per_serving=NutritionPerServing(0, 0, 0, 0, 0, 0, 0, 0, 0),
            difficulty="easy",
        )
        result = ExpansionResult(success=True, recipe=recipe, source_url="https://example.com")

        assert result.success is True
        assert result.recipe is not None
        assert result.source_url == "https://example.com"
        assert result.was_duplicate is False
        assert result.error_message == ""

    def test_expansion_result_failure(self):
        result = ExpansionResult(
            success=False,
            source_url="https://example.com",
            error_message="Failed to fetch page",
        )

        assert result.success is False
        assert result.recipe is None
        assert result.error_message == "Failed to fetch page"

    def test_expansion_result_duplicate(self):
        result = ExpansionResult(
            success=False,
            source_url="https://example.com",
            was_duplicate=True,
            error_message="Duplicate recipe",
        )

        assert result.success is False
        assert result.was_duplicate is True
        assert "Duplicate" in result.error_message


class TestLoadCroatiaIngredients:

    def test_load_croatia_ingredients_success(self, temp_data_dir, empty_store):
        expander = RecipeExpander(
            store=empty_store,
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            expanded_recipes_path=str(temp_data_dir / "expanded_recipes.json"),
        )

        assert len(expander._croatia_ingredients) > 0
        assert "onion" in expander._croatia_ingredients
        assert "lentils" in expander._croatia_ingredients

    def test_load_croatia_ingredients_file_not_found(self, tmp_path, empty_store):
        expander = RecipeExpander(
            store=empty_store,
            croatia_ingredients_path=str(tmp_path / "nonexistent.json"),
            expanded_recipes_path=str(tmp_path / "expanded_recipes.json"),
        )

        # Should not raise, just log warning and continue with empty set
        assert expander._croatia_ingredients == set()