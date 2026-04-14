"""Tests for shopping list generation."""

from datetime import date

from recepti.models import MealPlan
from recepti.shopping import (
    DAIRY_EGGS,
    DRY_GOODS,
    PRODUCE,
    SPICES,
    _get_ingredient_section,
    _normalize_unit,
    format_shopping_list,
    generate_shopping_list_from_recipes,
)


class TestShopping:
    def test_section_mapping_produce(self):
        assert _get_ingredient_section("spinach") == PRODUCE
        assert _get_ingredient_section("palak") == PRODUCE

    def test_section_mapping_dairy(self):
        assert _get_ingredient_section("milk") == DAIRY_EGGS
        assert _get_ingredient_section("paneer") == DAIRY_EGGS
        assert _get_ingredient_section("yogurt") == DAIRY_EGGS

    def test_section_mapping_dry_goods(self):
        assert _get_ingredient_section("rice") == DRY_GOODS
        assert _get_ingredient_section("toor_dal") == DRY_GOODS
        assert _get_ingredient_section("rajma") == DRY_GOODS

    def test_section_mapping_spices(self):
        assert _get_ingredient_section("cumin") == SPICES
        assert _get_ingredient_section("turmeric") == SPICES

    def test_normalize_unit(self):
        assert _normalize_unit("grams") == "g"
        assert _normalize_unit("kg") == "kg"
        assert _normalize_unit("tbsp") == "tbsp"
        assert _normalize_unit("teaspoon") == "tsp"
        assert _normalize_unit("L") == "L"

    def test_generate_shopping_list(self, sample_recipes):
        recipes_db = {r.id: r for r in sample_recipes}
        plan = {
            date.today(): MealPlan(
                date=date.today(),
                breakfast_id=1,
                lunch_id=2,
                dinner_id=3,
            )
        }
        shopping = generate_shopping_list_from_recipes(plan, recipes_db)
        assert PRODUCE in shopping
        assert DAIRY_EGGS in shopping
        assert DRY_GOODS in shopping

    def test_format_shopping_list(self, sample_recipes):
        recipes_db = {r.id: r for r in sample_recipes}
        plan = {
            date.today(): MealPlan(
                date=date.today(),
                breakfast_id=1,
                lunch_id=2,
                dinner_id=3,
            )
        }
        shopping = generate_shopping_list_from_recipes(plan, recipes_db)
        formatted = format_shopping_list(shopping)
        assert "Shopping List:" in formatted
        assert "[Dairy & Eggs]" in formatted
        assert "[Dry Goods & Grains]" in formatted
