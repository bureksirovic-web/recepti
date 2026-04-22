"""Tests for RecipePreloader (scheduler)."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from recepti.scheduler import LastExpansion, RecipePreloader


@pytest.fixture
def temp_data_dir(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    croatia_file = data_dir / "croatia_ingredients.json"
    croatia_file.write_text(json.dumps({
        "categories": {
            "vegetables": ["onion", "tomato", "potato", "spinach", "zucchini"],
            "legumes": ["lentils", "red lentils", "green lentils", "chickpeas", "white beans"],
            "dairy": ["milk", "yogurt", "eggs"],
            "pantry": ["olive oil", "salt", "pepper"],
        }
    }))
    return data_dir


@pytest.fixture
def last_expansion_file(temp_data_dir):
    return temp_data_dir / "last_expansion.json"


class TestRecipePreloaderInit:

    def test_init_loads_ingredients(self, temp_data_dir, last_expansion_file):
        preloader = RecipePreloader(
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            last_expansion_path=str(last_expansion_file),
        )
        assert len(preloader._all_ingredients) > 0
        assert "spinach" in preloader._all_ingredients
        assert "lentils" in preloader._all_ingredients

    def test_init_falls_back_on_missing_file(self, tmp_path):
        preloader = RecipePreloader(
            croatia_ingredients_path=str(tmp_path / "nonexistent.json"),
            last_expansion_path=str(tmp_path / "last.json"),
        )
        assert len(preloader._all_ingredients) > 0
        assert "lentils" in preloader._all_ingredients


class TestShouldRunToday:

    def test_should_run_today_returns_true_when_no_file(self, temp_data_dir, last_expansion_file):
        preloader = RecipePreloader(
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            last_expansion_path=str(last_expansion_file),
        )
        assert preloader._should_run_today() is True

    def test_should_run_today_returns_false_when_recently_run(self, temp_data_dir, last_expansion_file):
        last_expansion_file.write_text(json.dumps({
            "last_run": datetime.now().isoformat(),
            "ingredient": "lentils",
            "recipes_added": 2,
        }))
        preloader = RecipePreloader(
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            last_expansion_path=str(last_expansion_file),
        )
        assert preloader._should_run_today() is False

    def test_should_run_today_returns_true_after_24_hours(self, temp_data_dir, last_expansion_file):
        old_time = datetime.now() - timedelta(hours=25)
        last_expansion_file.write_text(json.dumps({
            "last_run": old_time.isoformat(),
            "ingredient": "lentils",
            "recipes_added": 2,
        }))
        preloader = RecipePreloader(
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            last_expansion_path=str(last_expansion_file),
        )
        assert preloader._should_run_today() is True


class TestGetLastExpansion:

    def test_get_last_expansion_returns_none_when_no_file(self, temp_data_dir, last_expansion_file):
        preloader = RecipePreloader(
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            last_expansion_path=str(last_expansion_file),
        )
        assert preloader.get_last_expansion() is None

    def test_get_last_expansion_returns_last_expansion(self, temp_data_dir, last_expansion_file):
        last_expansion_file.write_text(json.dumps({
            "last_run": "2024-01-15T10:30:00",
            "ingredient": "spinach",
            "recipes_added": 3,
        }))
        preloader = RecipePreloader(
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            last_expansion_path=str(last_expansion_file),
        )
        result = preloader.get_last_expansion()
        assert result is not None
        assert isinstance(result, LastExpansion)
        assert result.ingredient == "spinach"
        assert result.recipes_added == 3


class TestRunDaily:

    def test_run_daily_returns_false_when_already_ran(self, temp_data_dir, last_expansion_file):
        last_expansion_file.write_text(json.dumps({
            "last_run": datetime.now().isoformat(),
            "ingredient": "lentils",
            "recipes_added": 2,
        }))
        preloader = RecipePreloader(
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            last_expansion_path=str(last_expansion_file),
        )
        mock_expander = MagicMock()
        result = preloader.run_daily(mock_expander)
        assert result is False
        mock_expander.expand_ingredient.assert_not_called()

    def test_run_daily_returns_true_and_expands_when_should_run(self, temp_data_dir, last_expansion_file):
        preloader = RecipePreloader(
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            last_expansion_path=str(last_expansion_file),
        )
        mock_expander = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_expander.expand_ingredient.return_value = [mock_result]

        result = preloader.run_daily(mock_expander)

        assert result is True
        mock_expander.expand_ingredient.assert_called_once()
        call_args = mock_expander.expand_ingredient.call_args
        assert call_args[1]["max_recipes"] == 2

    def test_run_daily_saves_last_run(self, temp_data_dir, last_expansion_file):
        preloader = RecipePreloader(
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            last_expansion_path=str(last_expansion_file),
        )
        mock_expander = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_expander.expand_ingredient.return_value = [mock_result]

        preloader.run_daily(mock_expander)

        assert last_expansion_file.exists()
        data = json.loads(last_expansion_file.read_text())
        assert "last_run" in data
        assert data["recipes_added"] == 1


class TestPickRandomIngredient:

    def test_pick_random_ingredient_returns_valid_ingredient(self, temp_data_dir, last_expansion_file):
        preloader = RecipePreloader(
            croatia_ingredients_path=str(temp_data_dir / "croatia_ingredients.json"),
            last_expansion_path=str(last_expansion_file),
        )
        ingredient = preloader._pick_random_ingredient()
        assert ingredient in preloader._all_ingredients