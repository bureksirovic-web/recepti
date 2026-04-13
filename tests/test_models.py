"""Tests for models."""
import pytest
from datetime import date
from recepti.models import (
    Ingredient, NutritionPerServing, RecipeTags, Recipe,
    MealPlan, Child, DailyIntake, RecipeCollection,
)


class TestModels:
    def test_ingredient(self):
        i = Ingredient("rice", 200, "g")
        assert i.name == "rice"
        assert i.amount == 200
        assert i.unit == "g"

    def test_nutrition_per_serving(self):
        n = NutritionPerServing(
            calories=180, protein_g=8, carbs_g=30, fat_g=4,
            fiber_g=6, iron_mg=3, calcium_mg=50, folate_mcg=100, b12_mcg=0,
        )
        assert n.calories == 180
        assert n.protein_g == 8

    def test_recipe_tags(self):
        t = RecipeTags(cuisine="Punjabi", meal_type="lunch", dietary_tags=["vegetarian"])
        assert t.cuisine == "Punjabi"
        assert "vegetarian" in t.dietary_tags

    def test_recipe(self, sample_recipe):
        assert sample_recipe.id == 1
        assert sample_recipe.name == "Dal Tadka"
        assert len(sample_recipe.ingredients) == 6
        assert len(sample_recipe.instructions) == 4

    def test_meal_plan(self):
        mp = MealPlan(
            date=date.today(),
            breakfast_id=1,
            lunch_id=2,
            dinner_id=3,
        )
        assert mp.date == date.today()
        assert mp.breakfast_id == 1
        assert mp.lunch_id == 2
        assert mp.dinner_id == 3

    def test_child(self):
        c = Child(id=1, name="Alice", age_years=5.5, dislikes=["spinach"], favorites=[2])
        assert c.name == "Alice"
        assert "spinach" in c.dislikes

    def test_daily_intake(self):
        d = DailyIntake(
            child_id=1,
            date=date.today(),
            meal_type="lunch",
            recipe_id=3,
            amount_served=1.0,
            amount_eaten=0.8,
        )
        assert d.amount_eaten == 0.8

    def test_recipe_collection_find_by_ingredients(self, sample_recipes):
        coll = RecipeCollection(recipes=sample_recipes)
        results = coll.find_by_ingredients(["paneer"])
        assert len(results) >= 1
        assert results[0][0].name == "Paneer Butter Masala"

    def test_recipe_collection_find_by_tags(self, sample_recipes):
        coll = RecipeCollection(recipes=sample_recipes)
        # Empty meal_type matches any meal type, so South Indian returns 2 (Curd Rice + Rice with Sambhar)
        results = coll.find_by_tags(RecipeTags(cuisine="South Indian", meal_type=""))
        assert len(results) == 2
        names = {r.name for r in results}
        assert "Curd Rice" in names
        assert "Rice with Sambhar" in names