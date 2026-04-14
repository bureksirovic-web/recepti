"""Tests for nutrition estimation."""

from recepti.models import MealPlan, NutritionPerServing, Recipe, RecipeTags
from recepti.nutrition import (
    _convert_to_grams,
    _parse_ingredient_name,
    check_daily_balance,
    estimate_recipe_nutrition,
)


class TestNutrition:
    def test_parse_ingredient_name_aliases(self):
        assert _parse_ingredient_name("toor dal") == "toor_dal"
        assert _parse_ingredient_name("masoor dal") == "masoor_dal"
        assert _parse_ingredient_name("paneer") == "paneer"
        assert _parse_ingredient_name("cottage cheese") == "paneer"
        assert _parse_ingredient_name("spinach") == "palak"
        assert _parse_ingredient_name("rajma") == "rajma"

    def test_convert_to_grams_known(self):
        assert _convert_to_grams(100, "g") == 100
        assert _convert_to_grams(1, "kg") == 1000
        assert _convert_to_grams(2, "tbsp") == 30
        assert _convert_to_grams(1, "cup") == 200

    def test_estimate_recipe_nutrition(self, sample_recipe):
        result = estimate_recipe_nutrition(sample_recipe)
        assert "calories" in result
        assert "protein_g" in result
        assert result["calories"] > 0
        assert result["protein_g"] > 0

    def test_estimate_empty_recipe(self):
        recipe = Recipe(
            id=99,
            name="Empty",
            description="",
            ingredients=[],
            instructions=[],
            tags=RecipeTags(cuisine="", meal_type="", dietary_tags=[]),
            servings=1,
            prep_time_min=0,
            cook_time_min=0,
            nutrition_per_serving=NutritionPerServing(
                calories=0,
                protein_g=0,
                carbs_g=0,
                fat_g=0,
                fiber_g=0,
                iron_mg=0,
                calcium_mg=0,
                folate_mcg=0,
                b12_mcg=0,
            ),
            difficulty="easy",
        )
        result = estimate_recipe_nutrition(recipe)
        assert result["calories"] == 0

    def test_check_daily_balance(self, sample_recipes, sample_children):
        recipes_db = {r.id: r for r in sample_recipes}
        # Use first 3 recipes as today's plan
        plan = MealPlan(
            date=sample_children[0].age_years,
            breakfast_id=1,
            lunch_id=2,
            dinner_id=3,
        )
        assessments = check_daily_balance(plan, sample_children, recipes_db)
        assert len(assessments) == 3
        for child_id, assessment in assessments.items():
            assert "meets" in assessment
            assert "shortages" in assessment
            assert "child_name" in assessment
            assert "age_group" in assessment
