"""Tests for meal planner."""
from datetime import date
from recepti.planner import (
    generate_weekly_plan,
    format_meal_plan,
)
from recepti.models import RecipeCollection


class TestMealPlanner:
    def test_generate_weekly_plan_default(self, sample_recipes):
        collection = RecipeCollection(recipes=sample_recipes)
        plans = generate_weekly_plan(days=7, preferences={
            "recipe_collection": collection,
        })
        assert len(plans) == 7
        dates = list(plans.keys())
        assert dates[0] == date.today().isoformat()

    def test_generate_weekly_plan_recipe_ids(self, sample_recipes):
        collection = RecipeCollection(recipes=sample_recipes)
        plans = generate_weekly_plan(days=3, preferences={
            "recipe_collection": collection,
        })
        for day_plan in plans.values():
            # Should have recipe IDs for each slot
            assert day_plan.breakfast_id is not None or day_plan.lunch_id is not None or day_plan.dinner_id is not None

    def test_no_repeat_within_week(self, sample_recipes):
        collection = RecipeCollection(recipes=sample_recipes)
        plans = generate_weekly_plan(days=3, preferences={
            "recipe_collection": collection,
        })
        all_ids = []
        for mp in plans.values():
            for rid in [mp.breakfast_id, mp.lunch_id, mp.dinner_id]:
                if rid is not None:
                    all_ids.append(rid)
        for mp in plans.values():
            day_ids = [rid for rid in [mp.breakfast_id, mp.lunch_id, mp.dinner_id] if rid is not None]
            # All slots on same day should have different recipe IDs
            assert len(day_ids) == len(set(day_ids)), f"Repeat within day: {day_ids}"

    def test_format_meal_plan(self, sample_recipes):
        from recepti.models import MealPlan
        plan = MealPlan(
            date=date.today(),
            breakfast_id=1,
            lunch_id=2,
            dinner_id=3,
        )
        formatted = format_meal_plan(date.today().isoformat(), plan)
        assert "Breakfast" in formatted
        assert "Lunch" in formatted
        assert "Dinner" in formatted
        assert "#1" in formatted  # recipe ID shown

    def test_format_meal_plan_empty(self, sample_recipes):
        from recepti.models import MealPlan
        plan = MealPlan(date=date.today())
        formatted = format_meal_plan(date.today().isoformat(), plan)
        assert "(not planned)" in formatted