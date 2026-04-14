"""Tests for kid_tracker.py."""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from recepti.kid_tracker import KidMealHistory
from recepti.models import Ingredient, NutritionPerServing, Recipe, RecipeTags

# ─── Helpers ────────────────────────────────────────────────────────────────────


def make_nutrition(calories: float = 300, protein_g: float = 10) -> NutritionPerServing:
    return NutritionPerServing(
        calories=calories,
        protein_g=protein_g,
        carbs_g=50,
        fat_g=10,
        fiber_g=5,
        iron_mg=2,
        calcium_mg=50,
        folate_mcg=100,
        b12_mcg=1,
    )


def recent_date(days_ago: int = 0) -> str:
    """Return ISO date string for N days ago from today."""
    return (date.today() - timedelta(days=days_ago)).isoformat()


class FakeRecipeStore:
    """Minimal Recipe store for testing kid_tracker."""

    def __init__(self, recipes: list[Recipe]) -> None:
        self._recipes = {r.id: r for r in recipes}

    def get_recipe_by_id(self, recipe_id: int) -> Recipe | None:
        return self._recipes.get(recipe_id)


@pytest.fixture
def recipe_store() -> FakeRecipeStore:
    pasta = Recipe(
        id=1,
        name="Pasta with Marinara",
        description="Kid-friendly pasta",
        ingredients=[Ingredient(name="pasta", amount=100, unit="g")],
        instructions="Boil pasta. Add sauce.",
        tags=RecipeTags(cuisine="Italian", meal_type="lunch"),
        servings=2,
        prep_time_min=5,
        cook_time_min=20,
        nutrition_per_serving=make_nutrition(300, 10),
        difficulty="easy",
    )
    broccoli = Recipe(
        id=2,
        name="Steamed Broccoli",
        description="Green veggie side",
        ingredients=[Ingredient(name="broccoli", amount=50, unit="g")],
        instructions="Steam broccoli.",
        tags=RecipeTags(cuisine="American", meal_type="dinner"),
        servings=2,
        prep_time_min=2,
        cook_time_min=10,
        nutrition_per_serving=make_nutrition(50, 3),
        difficulty="easy",
    )
    pizza = Recipe(
        id=3,
        name="Cheese Pizza",
        description="Cheesy goodness",
        ingredients=[Ingredient(name="cheese", amount=80, unit="g")],
        instructions="Bake pizza.",
        tags=RecipeTags(cuisine="Italian", meal_type="lunch"),
        servings=2,
        prep_time_min=10,
        cook_time_min=15,
        nutrition_per_serving=make_nutrition(400, 15),
        difficulty="medium",
    )
    return FakeRecipeStore([pasta, broccoli, pizza])


@pytest.fixture
def history_file(tmp_path: Path) -> str:
    return str(tmp_path / ".kid_history.json")


@pytest.fixture
def tracker(history_file: str, recipe_store: FakeRecipeStore) -> KidMealHistory:
    t = KidMealHistory(storage_path=history_file)
    t._set_recipe_store(recipe_store)
    return t


# ─── Tests ─────────────────────────────────────────────────────────────────────


class TestKidMealHistoryInit:
    def test_new_tracker_starts_empty(
        self, history_file: str, recipe_store: FakeRecipeStore
    ) -> None:
        t = KidMealHistory(storage_path=history_file)
        t._set_recipe_store(recipe_store)
        assert t.get_child_favorites(child_id=1) == []
        assert t.get_child_dislikes(child_id=1) == []

    def test_loads_existing_history(self, history_file: str, recipe_store: FakeRecipeStore) -> None:
        yesterday = recent_date(1)
        data = {
            5: {
                "history": [
                    {
                        "recipe_id": 1,
                        "meal_type": "lunch",
                        "date": yesterday,
                        "amount_eaten": 0.9,
                        "notes": "",
                    },
                ],
                "favorites_cache": [],
                "dislikes_cache": [],
            }
        }
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        t = KidMealHistory(storage_path=history_file)
        t._set_recipe_store(recipe_store)
        assert len(t.get_child_favorites(child_id=5)) == 1


class TestRecordMeal:
    def test_record_meal_creates_child(self, tracker: KidMealHistory) -> None:
        tracker.record_meal(
            child_id=1,
            recipe_id=1,
            meal_type="lunch",
            date=recent_date(0),
            amount_eaten=0.8,
            notes="",
        )
        favorites = tracker.get_child_favorites(child_id=1)
        assert 1 in favorites

    def test_record_meal_invalidates_caches(self, tracker: KidMealHistory) -> None:
        tracker.record_meal(
            child_id=1,
            recipe_id=1,
            meal_type="lunch",
            date=recent_date(0),
            amount_eaten=0.9,
            notes="",
        )
        assert tracker._data[1]["favorites_cache"] == []
        assert tracker._data[1]["dislikes_cache"] == []


class TestGetChildFavorites:
    def test_favorites_ranked_by_amount(self, tracker: KidMealHistory) -> None:
        # Same recipe eaten twice (total 1.4), third recipe once (0.7)
        tracker.record_meal(
            child_id=1,
            recipe_id=1,
            meal_type="lunch",
            date=recent_date(2),
            amount_eaten=0.5,
            notes="",
        )
        tracker.record_meal(
            child_id=1,
            recipe_id=1,
            meal_type="dinner",
            date=recent_date(1),
            amount_eaten=0.9,
            notes="",
        )
        tracker.record_meal(
            child_id=1,
            recipe_id=3,
            meal_type="lunch",
            date=recent_date(0),
            amount_eaten=0.7,
            notes="",
        )
        favorites = tracker.get_child_favorites(child_id=1, limit=5)
        assert favorites == [1, 3]

    def test_no_history_returns_empty(self, tracker: KidMealHistory) -> None:
        assert tracker.get_child_favorites(child_id=999) == []


class TestGetChildDislikes:
    def test_dislikes_ingredients_from_low_eaten(self, tracker: KidMealHistory) -> None:
        # Recipe 2 = broccoli; eaten only 0.2 → disliked
        tracker.record_meal(
            child_id=1,
            recipe_id=2,
            meal_type="dinner",
            date=recent_date(0),
            amount_eaten=0.2,
            notes="hated it",
        )
        dislikes = tracker.get_child_dislikes(child_id=1)
        assert "broccoli" in dislikes

    def test_no_dislikes_if_all_eaten_well(self, tracker: KidMealHistory) -> None:
        tracker.record_meal(
            child_id=1,
            recipe_id=2,
            meal_type="dinner",
            date=recent_date(0),
            amount_eaten=0.9,
            notes="",
        )
        assert tracker.get_child_dislikes(child_id=1) == []

    def test_unknown_child_returns_empty(self, tracker: KidMealHistory) -> None:
        assert tracker.get_child_dislikes(child_id=999) == []


class TestGetChildHistory:
    def test_history_enriched_with_names(self, tracker: KidMealHistory) -> None:
        tracker.record_meal(
            child_id=1,
            recipe_id=1,
            meal_type="lunch",
            date=recent_date(0),
            amount_eaten=0.9,
            notes="",
        )
        history = tracker.get_child_history(child_id=1, days=30)
        assert len(history) == 1
        assert history[0]["recipe_name"] == "Pasta with Marinara"
        assert history[0]["amount_eaten"] == 0.9

    def test_history_respects_days_cutoff(self, tracker: KidMealHistory) -> None:
        # Record from 20 days ago — outside 7-day window
        tracker.record_meal(
            child_id=1,
            recipe_id=1,
            meal_type="lunch",
            date=recent_date(20),
            amount_eaten=0.9,
            notes="",
        )
        history = tracker.get_child_history(child_id=1, days=7)
        assert len(history) == 0

    def test_unknown_child_returns_empty(self, tracker: KidMealHistory) -> None:
        assert tracker.get_child_history(child_id=999) == []


class TestGetFamilySummary:
    def test_family_summary_includes_all_children(self, tracker: KidMealHistory) -> None:
        tracker.record_meal(
            child_id=1,
            recipe_id=1,
            meal_type="lunch",
            date=recent_date(0),
            amount_eaten=0.9,
            notes="",
        )
        tracker.record_meal(
            child_id=2,
            recipe_id=2,
            meal_type="dinner",
            date=recent_date(1),
            amount_eaten=0.2,
            notes="",
        )
        summary = tracker.get_family_summary(days=7)
        assert "1" in summary
        assert "2" in summary

    def test_dislikes_reflected_in_summary(self, tracker: KidMealHistory) -> None:
        tracker.record_meal(
            child_id=1,
            recipe_id=2,
            meal_type="dinner",
            date=recent_date(0),
            amount_eaten=0.1,
            notes="",
        )
        summary = tracker.get_family_summary(days=7)
        assert "broccoli" in summary["1"]["dislikes"]

    def test_meals_eaten_count(self, tracker: KidMealHistory) -> None:
        tracker.record_meal(
            child_id=1,
            recipe_id=1,
            meal_type="lunch",
            date=recent_date(0),
            amount_eaten=0.5,
            notes="",
        )
        tracker.record_meal(
            child_id=1,
            recipe_id=2,
            meal_type="dinner",
            date=recent_date(1),
            amount_eaten=0.5,
            notes="",
        )
        summary = tracker.get_family_summary(days=7)
        assert summary["1"]["meals_eaten"] == 2

    def test_top_recipes_in_summary(self, tracker: KidMealHistory) -> None:
        tracker.record_meal(
            child_id=1,
            recipe_id=1,
            meal_type="lunch",
            date=recent_date(0),
            amount_eaten=0.9,
            notes="",
        )
        tracker.record_meal(
            child_id=1,
            recipe_id=3,
            meal_type="dinner",
            date=recent_date(1),
            amount_eaten=0.9,
            notes="",
        )
        summary = tracker.get_family_summary(days=7)
        assert "Pasta with Marinara" in summary["1"]["most_eaten_recipes"]
        assert "Cheese Pizza" in summary["1"]["most_eaten_recipes"]
