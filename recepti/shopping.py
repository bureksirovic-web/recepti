"""Shopping list generation for meal plans."""

from collections import defaultdict
from datetime import date
from typing import Any

from recepti.models import Recipe, MealPlan


# Store section definitions
PRODUCE = "Produce"
DAIRY_EGGS = "Dairy & Eggs"
DRY_GOODS = "Dry Goods & Grains"
SPICES = "Spices"
OTHER = "Other"

STORE_SECTIONS = [PRODUCE, DAIRY_EGGS, DRY_GOODS, SPICES, OTHER]


# Ingredient to store section mapping
INGREDIENT_SECTIONS: dict[str, str] = {
    # Produce (vegetables, fresh items)
    "palak": PRODUCE,
    "vegetables": PRODUCE,
    "spinach": PRODUCE,
    "mixed vegetables": PRODUCE,
    "sabzi": PRODUCE,
    
    # Dairy & Eggs
    "milk": DAIRY_EGGS,
    "whole milk": DAIRY_EGGS,
    "cow milk": DAIRY_EGGS,
    "yogurt": DAIRY_EGGS,
    "curd": DAIRY_EGGS,
    "dahi": DAIRY_EGGS,
    "paneer": DAIRY_EGGS,
    "cottage cheese": DAIRY_EGGS,
    "eggs": DAIRY_EGGS,
    "egg": DAIRY_EGGS,
    
    # Dry Goods & Grains
    "rice": DRY_GOODS,
    "basmati rice": DRY_GOODS,
    "white rice": DRY_GOODS,
    "roti": DRY_GOODS,
    "chapati": DRY_GOODS,
    "phulka": DRY_GOODS,
    "toor_dal": DRY_GOODS,
    "toor dal": DRY_GOODS,
    "arhar dal": DRY_GOODS,
    "tuvar dal": DRY_GOODS,
    "masoor_dal": DRY_GOODS,
    "masoor dal": DRY_GOODS,
    "red lentils": DRY_GOODS,
    "chana_dal": DRY_GOODS,
    "chana dal": DRY_GOODS,
    "bengal gram": DRY_GOODS,
    "rajma": DRY_GOODS,
    "kidney beans": DRY_GOODS,
    "peanuts": DRY_GOODS,
    "peanut": DRY_GOODS,
    "cashews": DRY_GOODS,
    "cashew": DRY_GOODS,
    "cashew nuts": DRY_GOODS,
    
    # Spices
    "turmeric": SPICES,
    "cumin": SPICES,
    "cumin seeds": SPICES,
    "coriander": SPICES,
    "coriander powder": SPICES,
    "garam masala": SPICES,
    "chili powder": SPICES,
    "red chili": SPICES,
    "green chili": SPICES,
    "ginger": SPICES,
    "garlic": SPICES,
    "salt": SPICES,
    "black pepper": SPICES,
    "cinnamon": SPICES,
    "cardamom": SPICES,
    "cloves": SPICES,
}


def _parse_amount_str(amount: str) -> float:
    """Parse amount string like '1/2', '3-4', 'to taste' to float. Returns 0 on failure."""
    if isinstance(amount, float):
        return amount
    if isinstance(amount, int):
        return float(amount)
    s = str(amount).strip().lower()
    if s in ("", "to taste", "as needed", "a pinch", "pinch"):
        return 0.0
    if "/" in s:
        parts = s.split("/")
        if len(parts) == 2:
            try:
                return float(parts[0]) / float(parts[1])
            except ValueError:
                return 0.0
    if "-" in s:
        parts = s.split("-")
        try:
            return (float(parts[0]) + float(parts[1])) / 2
        except ValueError:
            return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _get_ingredient_section(ingredient_name: str) -> str:
    """Determine the store section for an ingredient."""
    name_lower = ingredient_name.lower().strip()
    
    # Check exact match first
    if name_lower in INGREDIENT_SECTIONS:
        return INGREDIENT_SECTIONS[name_lower]
    
    # Check partial matches
    for key, section in INGREDIENT_SECTIONS.items():
        if key in name_lower or name_lower in key:
            return section
    
    return OTHER


def _normalize_unit(unit: str) -> str:
    """Normalize unit strings for consistent grouping."""
    unit_lower = unit.lower().strip()
    
    if unit_lower in ("g", "gram", "grams"):
        return "g"
    elif unit_lower in ("kg", "kilogram", "kilograms"):
        return "kg"
    elif unit_lower in ("ml", "milliliter", "milliliters"):
        return "ml"
    elif unit_lower in ("l", "liter", "liters"):
        return "L"
    elif unit_lower in ("tbsp", "tablespoon", "tablespoons"):
        return "tbsp"
    elif unit_lower in ("tsp", "teaspoon", "teaspoons"):
        return "tsp"
    elif unit_lower in ("oz", "ounce", "ounces"):
        return "oz"
    elif unit_lower in ("lb", "pound", "pounds"):
        return "lb"
    else:
        return unit_lower if unit_lower else "unit"


def _can_combine_units(unit1: str, unit2: str) -> bool:
    """Check if two units can be combined (same measurement system)."""
    u1 = _normalize_unit(unit1)
    u2 = _normalize_unit(unit2)
    if u1 == u2:
        return True
    
    # Compatible units
    compatible_sets = [
        {"g", "gram", "grams"},
        {"kg", "kilogram"},
        {"ml", "milliliter"},
        {"l", "liter"},
        {"tbsp", "tablespoon"},
        {"tsp", "teaspoon"},
    ]
    
    for s in compatible_sets:
        if u1 in s and u2 in s:
            return True
    
    return False


def _convert_to_base_unit(amount: float, unit: str) -> tuple[float, str]:
    """Convert amount to base unit for combining."""
    unit_lower = unit.lower().strip()
    
    # Volume conversions
    if unit_lower in ("tbsp", "tablespoon", "tablespoons"):
        return amount * 15, "ml"
    elif unit_lower in ("tsp", "teaspoon", "teaspoons"):
        return amount * 5, "ml"
    elif unit_lower in ("cup", "cups"):
        return amount * 240, "ml"
    elif unit_lower in ("l", "liter", "liters"):
        return amount * 1000, "ml"
    
    # Weight conversions
    elif unit_lower in ("kg", "kilogram", "kilograms"):
        return amount * 1000, "g"
    elif unit_lower in ("oz", "ounce", "ounces"):
        return amount * 28.35, "g"
    elif unit_lower in ("lb", "pound", "pounds"):
        return amount * 453.6, "g"
    
    return amount, _normalize_unit(unit)


def generate_shopping_list(plan: dict[str | date, MealPlan]) -> dict[str, list[dict[str, Any]]]:
    """
    Generate a shopping list grouped by store section.
    
    Args:
        plan: Dict of {date_str or date: MealPlan}
    
    Returns:
        Dict of {section_name: list of {item, amount, unit}}
    """
    # Aggregate all ingredients
    ingredient_totals: dict[str, dict[str, float]] = defaultdict(lambda: {"amount": 0, "unit": "g"})
    
    for day_date, meal_plan in plan.items():
        # Get recipe IDs for this day
        recipe_ids = [
            meal_plan.breakfast_id,
            meal_plan.lunch_id,
            meal_plan.dinner_id,
        ]
        
        for recipe_id in recipe_ids:
            if recipe_id is None:
                continue
            # In real implementation, would look up recipe from database
            # For now, skip recipe lookup - would need recipes_db passed in
    
    # Build grouped result
    result: dict[str, list[dict[str, Any]]] = {section: [] for section in STORE_SECTIONS}
    
    for item_name, totals in ingredient_totals.items():
        section = _get_ingredient_section(item_name)
        result[section].append({
            "item": item_name,
            "amount": round(totals["amount"], 2),
            "unit": totals["unit"],
        })
    
    # Sort each section alphabetically
    for section in result:
        result[section].sort(key=lambda x: x["item"])
    
    return result


def generate_shopping_list_from_recipes(
    plan: dict[str | date, MealPlan],
    recipes_db: dict[int, Recipe],
) -> dict[str, list[dict[str, Any]]]:
    """
    Generate shopping list from a meal plan using a recipe database.
    
    Args:
        plan: Dict of {date_str or date: MealPlan}
        recipes_db: Dict mapping recipe ID to Recipe
    
    Returns:
        Dict of {section_name: list of {item, amount, unit}}
    """
    # Aggregate all ingredients
    aggregated: dict[str, tuple[float, str]] = {}
    
    for day_date, meal_plan in plan.items():
        for recipe_id in [meal_plan.breakfast_id, meal_plan.lunch_id, meal_plan.dinner_id]:
            if recipe_id is None or recipe_id not in recipes_db:
                continue
            
            recipe = recipes_db[recipe_id]
            for ingredient in recipe.ingredients:
                key = ingredient.name.lower().strip()
                unit = _normalize_unit(ingredient.unit)
                amt = _parse_amount_str(ingredient.amount)

                if key in aggregated:
                    existing_amount, existing_unit = aggregated[key]
                    if _can_combine_units(unit, existing_unit):
                        # Combine amounts
                        new_amount = existing_amount + amt
                        aggregated[key] = (new_amount, unit)
                    else:
                        # Can't combine different unit systems - add as separate entry
                        aggregated[key] = (existing_amount + amt, unit)
                else:
                    aggregated[key] = (amt, unit)
    
    # Group by store section
    result: dict[str, list[dict[str, Any]]] = {section: [] for section in STORE_SECTIONS}
    
    for item_name, (amount, unit) in aggregated.items():
        section = _get_ingredient_section(item_name)
        result[section].append({
            "item": item_name,
            "amount": round(amount, 2),
            "unit": unit,
        })
    
    # Sort each section alphabetically by item name
    for section in result:
        result[section].sort(key=lambda x: x["item"])
    
    return result


def format_shopping_list(shopping: dict[str, list[dict[str, Any]]]) -> str:
    """Format a shopping list for display."""
    lines = ["Shopping List:", ""]
    
    for section in STORE_SECTIONS:
        items = shopping.get(section, [])
        if not items:
            continue
        
        lines.append(f"[{section}]")
        for item in items:
            if item["unit"]:
                lines.append(f"  - {item['item']}: {item['amount']} {item['unit']}")
            else:
                lines.append(f"  - {item['item']}: {item['amount']}")
        lines.append("")
    
    return "\n".join(lines).strip()