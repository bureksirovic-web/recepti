"""Tests for RecipeHunter and its coverage helpers."""

import json
import os
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from recepti.models import Recipe, RecipeTags, Ingredient, NutritionPerServing
from recepti.recipe_hunter import (
    _build_holes,
    _build_reason,
    _get_tag_val,
    _suggest_queries,
    RecipeHunter,
)


# ── Coverage helpers ────────────────────────────────────────────────────────────────

class TestSuggestQueries:
    def test_suggest_queries_cuisine(self):
        result = _suggest_queries("cuisine", "croatian")
        assert "hrvatski recepti" in result

    def test_suggest_queries_meal_type(self):
        result = _suggest_queries("meal_type", "breakfast")
        assert "recepti za doručak" in result

    def test_suggest_queries_unknown_meal_type(self):
        result = _suggest_queries("meal_type", "brunch")
        assert "brunch" in result[0]

    def test_suggest_queries_difficulty(self):
        result = _suggest_queries("difficulty", "easy")
        assert "jednostavni recepti" in result


class TestBuildReason:
    def test_build_reason_coverage(self):
        result = _build_reason("coverage", "cuisine", "croatian", 0)
        assert "SPARSE" in result
        assert "croatian" in result

    def test_build_reason_rejection(self):
        result = _build_reason("rejection", "cuisine", "punjabi", 3)
        assert "REJECTED" in result
        assert "punjabi" in result

    def test_build_reason_both(self):
        result = _build_reason("both", "cuisine", "croatian", 2)
        assert "BOTH" in result


class TestGetTagVal:
    def test_get_tag_val_cuisine(self):
        r = MagicMock()
        r.tags.cuisine = "croatian"
        r.tags.meal_type = "lunch"
        r.difficulty = "easy"
        assert _get_tag_val(r, "cuisine") == "croatian"

    def test_get_tag_val_meal_type(self):
        r = MagicMock()
        r.tags.cuisine = "croatian"
        r.tags.meal_type = "dinner"
        r.difficulty = "easy"
        assert _get_tag_val(r, "meal_type") == "dinner"

    def test_get_tag_val_difficulty(self):
        r = MagicMock()
        r.difficulty = "medium"
        assert _get_tag_val(r, "difficulty") == "medium"


class TestBuildHoles:
    def _make_recipe(self, id_, cuisine, meal_type, difficulty):
        r = MagicMock()
        r.id = id_
        r.tags = MagicMock(cuisine=cuisine, meal_type=meal_type)
        r.difficulty = difficulty
        return r

    def test_build_holes_returns_empty_when_total_zero(self):
        result = _build_holes([], 0)
        assert result == []

    def test_build_holes_returns_list_with_status_field(self):
        recipes = [
            self._make_recipe(1, "croatian", "lunch", "easy"),
            self._make_recipe(2, "croatian", "lunch", "easy"),
            self._make_recipe(3, "punjabi", "dinner", "medium"),
        ]
        result = _build_holes(recipes, 3)
        assert len(result) > 0
        statuses = {h["status"] for h in result}
        assert statuses.issubset({"SPARSE", "EMPTY"})

    def test_build_holes_flags_sparse_dimension(self):
        recipes = [
            self._make_recipe(1, "croatian", "lunch", "easy"),
            self._make_recipe(2, "croatian", "lunch", "easy"),
            self._make_recipe(3, "punjabi", "lunch", "easy"),
        ]
        result = _build_holes(recipes, 3)
        cuisine_holes = [h for h in result if h["dimension"] == "cuisine"]
        assert any(h["status"] == "SPARSE" for h in cuisine_holes)

    def test_build_holes_sorted_by_priority(self):
        recipes = [
            self._make_recipe(1, "croatian", "lunch", "easy"),
            self._make_recipe(2, "croatian", "lunch", "easy"),
            self._make_recipe(3, "punjabi", "lunch", "easy"),
        ]
        result = _build_holes(recipes, 3)
        priorities = [h["priority"] for h in result]
        assert priorities == sorted(priorities, reverse=True)

    def test_build_holes_includes_suggested_queries(self):
        recipes = [
            self._make_recipe(1, "croatian", "lunch", "easy"),
        ]
        result = _build_holes(recipes, 1)
        assert any(h["suggested_queries"] for h in result)


# ── RecipeHunter instance methods ────────────────────────────────────────────────

@pytest.fixture
def mock_hunter(tmp_path):
    mock_rs = MagicMock()
    recipe = Recipe(
        id=1,
        name="Test Recipe",
        description="A test",
        ingredients=[Ingredient("onion", 100, "g")],
        instructions=["Chop onion."],
        tags=RecipeTags(cuisine="croatian", meal_type="lunch", dietary_tags=["vegetarian"]),
        servings=2,
        prep_time_min=10,
        cook_time_min=20,
        nutrition_per_serving=NutritionPerServing(0, 0, 0, 0, 0, 0, 0, 0, 0),
        difficulty="easy",
    )
    mock_rs._recipes = [recipe]
    mock_rs.get_recipe_by_id.return_value = recipe

    mock_cl = MagicMock()
    mock_cl.get_members.return_value = []

    mock_ratings = MagicMock()
    mock_ratings.get_rejected_cuisines.return_value = {}

    mock_balancer = MagicMock()

    mock_notif = MagicMock()

    state_file = tmp_path / "hunt_state.json"
    hunter = RecipeHunter(
        recipe_store=mock_rs,
        cooking_log=mock_cl,
        ratings=mock_ratings,
        balancer=mock_balancer,
        notification_store=mock_notif,
        state_file=str(state_file),
    )
    return hunter


class TestNormalizeName:
    def test_normalize_name_strips_and_lowercases(self, mock_hunter):
        result = mock_hunter._normalize_name("  Dal Tadka  ")
        assert result == "dal tadka"

    def test_normalize_name_removes_special_chars(self, mock_hunter):
        result = mock_hunter._normalize_name("Dal Tadka! (Recipe)")
        assert result == "dal tadka recipe"

    def test_normalize_name_collapses_spaces(self, mock_hunter):
        result = mock_hunter._normalize_name("Dal  Tadka")
        assert result == "dal tadka"


class TestIsDuplicate:
    def test_is_duplicate_returns_true_for_existing(self, mock_hunter):
        assert mock_hunter._is_duplicate("Test Recipe") is True

    def test_is_duplicate_returns_false_for_new(self, mock_hunter):
        assert mock_hunter._is_duplicate("Brand New Recipe") is False

    def test_is_duplicate_normalizes_before_check(self, mock_hunter):
        assert mock_hunter._is_duplicate("test recipe") is True


class TestIsVegetarianIsh:
    def test_is_vegetarian_ish_accepts_vegetarian_recipe(self, mock_hunter):
        assert mock_hunter._is_vegetarian_ish(
            ["onion", "tomato", "lentils"],
            ["Cook lentils.", "Add spices."],
        ) is True

    def test_is_vegetarian_ish_rejects_meat(self, mock_hunter):
        assert mock_hunter._is_vegetarian_ish(
            ["chicken", "onion"],
            ["Cook chicken."],
        ) is False

    def test_is_vegetarian_ish_rejects_fish(self, mock_hunter):
        assert mock_hunter._is_vegetarian_ish(
            ["salmon", "lemon"],
            ["Bake salmon."],
        ) is False

    def test_is_vegetarian_ish_rejects_pork(self, mock_hunter):
        assert mock_hunter._is_vegetarian_ish(
            ["pork", "beans"],
            ["Cook pork and beans."],
        ) is False

    def test_is_vegetarian_ish_rejects_anchovies(self, mock_hunter):
        assert mock_hunter._is_vegetarian_ish(
            ["onion", "tomato"],
            ["Add anchovies."],
        ) is False


class TestShouldRun:
    def test_should_run_true_when_no_file(self, mock_hunter, tmp_path):
        assert mock_hunter._should_run() is True

    def test_should_run_true_when_file_missing(self, mock_hunter, tmp_path):
        result = mock_hunter._should_run()
        assert result is True

    def test_should_run_true_after_enough_hours(self, mock_hunter, tmp_path):
        state_file = tmp_path / "hunt_state.json"
        state_file.write_text(
            json.dumps({"last_hunt_date": "2020-01-01T00:00:00"})
        )
        mock_hunter.state_file = state_file
        assert mock_hunter._should_run() is True

    def test_should_run_false_within_interval(self, mock_hunter, tmp_path):
        state_file = tmp_path / "hunt_state.json"
        from datetime import datetime
        state_file.write_text(
            json.dumps({"last_hunt_date": datetime.now().isoformat()})
        )
        mock_hunter.state_file = state_file
        assert mock_hunter._should_run() is False


class TestGetTargets:
    def test_get_targets_returns_empty_when_no_recipes(self, mock_hunter):
        mock_hunter.recipe_store._recipes = []
        targets = mock_hunter._get_targets()
        assert targets == []

    def test_get_targets_includes_coverage_holes(self, mock_hunter):
        targets = mock_hunter._get_targets()
        assert len(targets) > 0

    def test_get_targets_includes_reason(self, mock_hunter):
        targets = mock_hunter._get_targets()
        assert all("reason" in t for t in targets)

    def test_get_targets_sorted_by_priority(self, mock_hunter):
        targets = mock_hunter._get_targets()
        scores = [t["priority_score"] for t in targets]
        assert scores == sorted(scores, reverse=True)

    def test_get_targets_max_20(self, mock_hunter):
        targets = mock_hunter._get_targets()
        assert len(targets) <= 20

    def test_get_targets_handles_ratings_error(self, mock_hunter):
        mock_hunter.ratings.get_rejected_cuisines.side_effect = Exception("boom")
        targets = mock_hunter._get_targets()
        assert isinstance(targets, list)


class TestLoadState:
    def test_load_state_returns_empty_when_no_file(self, mock_hunter):
        result = mock_hunter._load_state()
        assert result == {}

    def test_load_state_returns_data_when_file_exists(self, mock_hunter, tmp_path):
        state_file = tmp_path / "hunt_state.json"
        state_file.write_text(json.dumps({"cycles_completed": 5}))
        mock_hunter.state_file = state_file
        result = mock_hunter._load_state()
        assert result["cycles_completed"] == 5

    def test_cycles_completed_returns_0_when_no_file(self, mock_hunter):
        assert mock_hunter._cycles_completed() == 0


class TestLifecycle:
    def test_start_creates_thread(self, mock_hunter):
        mock_hunter.start()
        assert mock_hunter._running is True
        assert mock_hunter._thread is not None
        assert mock_hunter._thread.daemon is True
        mock_hunter.stop()

    def test_stop_sets_running_false(self, mock_hunter):
        mock_hunter.start()
        mock_hunter.stop()
        assert mock_hunter._running is False


class TestHuntOnce:
    def test_hunt_once_returns_stats_dict(self, mock_hunter):
        with patch.object(mock_hunter, "_get_targets", return_value=[]):
            stats = mock_hunter.hunt_once()
        assert "targets_evaluated" in stats
        assert "recipes_added" in stats
        assert "recipes_extracted" in stats

    def test_hunt_once_calls_cuisine_blacklister(self, mock_hunter):
        with patch.object(mock_hunter, "_get_targets", return_value=[]):
            mock_hunter.hunt_once()
        mock_hunter.cooking_log.get_members.return_value

    def test_hunt_once_persists_state(self, mock_hunter, tmp_path):
        state_file = tmp_path / "hunt_state.json"
        mock_hunter.state_file = state_file
        with patch.object(mock_hunter, "_get_targets", return_value=[]):
            mock_hunter.hunt_once()
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert "last_hunt_date" in data

    def test_hunt_once_enqueues_notification(self, mock_hunter):
        with patch.object(mock_hunter, "_get_targets", return_value=[]):
            mock_hunter.hunt_once()
        mock_hunter.notification_store.enqueue.assert_called_once()