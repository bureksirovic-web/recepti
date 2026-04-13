"""Nutrition estimation for vegetarian recipes."""

from recepti.models import Recipe, MealPlan, Child, NutritionPerServing, Ingredient

# Lookup table: ingredient name -> nutrition per 100g
# Values are approximate for common Indian vegetarian ingredients
NUTRITION_DB: dict[str, dict[str, float]] = {
    # Lentils (dried, raw) - per 100g
    "toor_dal": {"calories": 364, "protein_g": 22, "carbs_g": 60, "fat_g": 1.4, "fiber_g": 15, "iron_mg": 5, "calcium_mg": 130, "folate_mcg": 423, "b12_mcg": 0},
    "masoor_dal": {"calories": 352, "protein_g": 25, "carbs_g": 60, "fat_g": 1, "fiber_g": 31, "iron_mg": 7, "calcium_mg": 107, "folate_mcg": 90, "b12_mcg": 0},
    "chana_dal": {"calories": 364, "protein_g": 17, "carbs_g": 60, "fat_g": 3, "fiber_g": 17, "iron_mg": 7, "calcium_mg": 59, "folate_mcg": 310, "b12_mcg": 0},
    "rajma": {"calories": 352, "protein_g": 22, "carbs_g": 60, "fat_g": 1, "fiber_g": 15, "iron_mg": 7, "calcium_mg": 140, "folate_mcg": 462, "b12_mcg": 0},
    
    # Vegetables - per 100g
    "palak": {"calories": 23, "protein_g": 2.9, "carbs_g": 3.6, "fat_g": 0.4, "fiber_g": 2.2, "iron_mg": 2.7, "calcium_mg": 99, "folate_mcg": 194, "b12_mcg": 0},
    "vegetables": {"calories": 25, "protein_g": 1.5, "carbs_g": 5, "fat_g": 0.2, "fiber_g": 2, "iron_mg": 1, "calcium_mg": 50, "folate_mcg": 80, "b12_mcg": 0},
    
    # Dairy - per 100g
    "paneer": {"calories": 265, "protein_g": 18, "carbs_g": 1.2, "fat_g": 21, "fiber_g": 0, "iron_mg": 0.5, "calcium_mg": 480, "folate_mcg": 10, "b12_mcg": 0.8},
    "milk": {"calories": 42, "protein_g": 3.4, "carbs_g": 5, "fat_g": 1, "fiber_g": 0, "iron_mg": 0.1, "calcium_mg": 125, "folate_mcg": 5, "b12_mcg": 0.4},
    "yogurt": {"calories": 59, "protein_g": 10, "carbs_g": 3.6, "fat_g": 0.7, "fiber_g": 0, "iron_mg": 0.1, "calcium_mg": 110, "folate_mcg": 4, "b12_mcg": 0.5},
    "eggs": {"calories": 155, "protein_g": 13, "carbs_g": 1.1, "fat_g": 11, "fiber_g": 0, "iron_mg": 1.8, "calcium_mg": 56, "folate_mcg": 47, "b12_mcg": 1.1},
    
    # Grains - per 100g
    "rice": {"calories": 360, "protein_g": 7, "carbs_g": 79, "fat_g": 0.6, "fiber_g": 1.4, "iron_mg": 0.8, "calcium_mg": 10, "folate_mcg": 8, "b12_mcg": 0},
    "roti": {"calories": 320, "protein_g": 10, "carbs_g": 64, "fat_g": 3, "fiber_g": 6, "iron_mg": 2, "calcium_mg": 40, "folate_mcg": 20, "b12_mcg": 0},
    
    # Nuts - per 100g
    "peanuts": {"calories": 567, "protein_g": 26, "carbs_g": 16, "fat_g": 49, "fiber_g": 8, "iron_mg": 4.6, "calcium_mg": 92, "folate_mcg": 240, "b12_mcg": 0},
    "cashews": {"calories": 553, "protein_g": 18, "carbs_g": 30, "fat_g": 44, "fiber_g": 3, "iron_mg": 6.7, "calcium_mg": 37, "folate_mcg": 69, "b12_mcg": 0},
}

# Unit to grams conversion for common units
UNIT_CONVERSION: dict[str, float] = {
    "g": 1,
    "gram": 1,
    "grams": 1,
    "kg": 1000,
    "kilogram": 1000,
    "oz": 28.35,
    "ounce": 28.35,
    "ounces": 28.35,
    "lb": 453.6,
    "pound": 453.6,
    "pounds": 453.6,
    "cup": 200,
    "cups": 200,
    "tbsp": 15,
    "tablespoon": 15,
    "tablespoons": 15,
    "tsp": 5,
    "teaspoon": 5,
    "teaspoons": 5,
    "piece": 100,
    "pieces": 100,
    "whole": 150,
    "medium": 80,
    "small": 50,
    "large": 120,
    "liter": 1000,
    "litre": 1000,
    "ml": 1,
    "milliliter": 1,
    "mls": 1,
}


def _parse_ingredient_name(name: str) -> str:
    """Normalize ingredient name to match lookup keys."""
    name = name.lower().strip()
    # Common aliases
    aliases = {
        "toor dal": "toor_dal",
        "arhar dal": "toor_dal",
        "tuvar dal": "toor_dal",
        "masoor dal": "masoor_dal",
        "red lentils": "masoor_dal",
        "chana dal": "chana_dal",
        "bengal gram": "chana_dal",
        "rajma": "rajma",
        "kidney beans": "rajma",
        "spinach": "palak",
        "paneer": "paneer",
        "cottage cheese": "paneer",
        "egg": "eggs",
        "egg whites": "eggs",
        "white rice": "rice",
        "basmati rice": "rice",
        "chapati": "roti",
        "phulka": "roti",
        "mixed vegetables": "vegetables",
        "sabzi": "vegetables",
        "curry vegetables": "vegetables",
        "cow milk": "milk",
        "whole milk": "milk",
        "dahi": "yogurt",
        "curd": "yogurt",
        "peanut": "peanuts",
        "roasted peanuts": "peanuts",
        "cashew": "cashews",
        "cashew nuts": "cashews",
    }
    if name in aliases:
        return aliases[name]
    return name


def _convert_to_grams(amount: float, unit: str) -> float:
    """Convert amount in given unit to grams."""
    unit_lower = unit.lower().strip()
    if unit_lower in ("pc", "pcs", "slice", "slices"):
        return amount * 100  # default piece weight
    factor = UNIT_CONVERSION.get(unit_lower, 100)  # default 100g per unknown unit
    return amount * factor


def estimate_recipe_nutrition(recipe: Recipe) -> dict:
    """
    Estimate nutrition for a Recipe from its ingredients list.
    
    Returns dict with keys: calories, protein_g, carbs_g, fat_g, fiber_g,
    iron_mg, calcium_mg, folate_mcg, b12_mcg
    """
    totals = {nutrient: 0.0 for nutrient in 
              ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g",
               "iron_mg", "calcium_mg", "folate_mcg", "b12_mcg"]}
    
    for ingredient in recipe.ingredients:
        name_key = _parse_ingredient_name(ingredient.name)
        
        if name_key not in NUTRITION_DB:
            # Skip unknown ingredients (could log warning)
            continue
        
        nutrition = NUTRITION_DB[name_key]
        grams = _convert_to_grams(ingredient.amount, ingredient.unit)
        factor = grams / 100.0  # nutrition DB is per 100g
        
        for nutrient in totals:
            totals[nutrient] += nutrition.get(nutrient, 0) * factor
    
    # Handle empty recipe
    servings = max(recipe.servings, 1)
    per_serving = {nutrient: round(val / servings, 2) for nutrient, val in totals.items()}
    return per_serving


# Child age group nutritional needs (daily requirements)
CHILD_AGE_GROUPS = [
    {
        "name": "toddler",
        "ages": "1-3",
        "daily_needs": {
            "protein_g": 13,
            "iron_mg": 7,
            "calcium_mg": 700,
            "folate_mcg": 150,
            "b12_mcg": 1.0,
        },
    },
    {
        "name": "preschooler",
        "ages": "4-5",
        "daily_needs": {
            "protein_g": 19,
            "iron_mg": 10,
            "calcium_mg": 1000,
            "folate_mcg": 200,
            "b12_mcg": 1.5,
        },
    },
    {
        "name": "schoolager",
        "ages": "6-9",
        "daily_needs": {
            "protein_g": 34,
            "iron_mg": 10,
            "calcium_mg": 1300,
            "folate_mcg": 300,
            "b12_mcg": 2.0,
        },
    },
    {
        "name": "preadolescent",
        "ages": "10-12",
        "daily_needs": {
            "protein_g": 36,
            "iron_mg": 12,
            "calcium_mg": 1300,
            "folate_mcg": 400,
            "b12_mcg": 2.5,
        },
    },
]


def _get_age_group(age_years: float) -> dict:
    """Get the age group definition for a child's age."""
    age = int(age_years)
    if age <= 3:
        return CHILD_AGE_GROUPS[0]  # toddler
    elif age <= 5:
        return CHILD_AGE_GROUPS[1]  # preschooler
    elif age <= 9:
        return CHILD_AGE_GROUPS[2]  # schoolager
    else:
        return CHILD_AGE_GROUPS[3]  # preadolescent


def _get_nutrients_from_meal_plan(day_plan: MealPlan, recipes_db: dict[int, Recipe]) -> dict:
    """Sum nutrition across all meals in a day plan."""
    totals = {nutrient: 0.0 for nutrient in 
              ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g",
               "iron_mg", "calcium_mg", "folate_mcg", "b12_mcg"]}
    
    for meal_id in [day_plan.breakfast_id, day_plan.lunch_id, day_plan.dinner_id]:
        if meal_id and meal_id in recipes_db:
            recipe = recipes_db[meal_id]
            nutrition = estimate_recipe_nutrition(recipe)
            for nutrient, value in nutrition.items():
                totals[nutrient] += value
    
    return totals


def check_daily_balance(day_plan: MealPlan, children: list[Child], recipes_db: dict[int, Recipe] | None = None) -> dict:
    """
    Assess whether meals cover protein, iron, calcium, folate, b12 for growing kids.
    
    Returns dict with per-child assessment of whether meals cover daily needs.
    """
    if recipes_db is None:
        # Build a simple lookup from day plan if not provided
        recipes_db = {}
    
    day_nutrition = _get_nutrients_from_meal_plan(day_plan, recipes_db)
    
    assessments = {}
    for child in children:
        age_group = _get_age_group(child.age_years)
        needs = age_group["daily_needs"]
        
        assessment = {
            "child_id": child.id,
            "child_name": child.name,
            "age_group": age_group["name"],
            "age_years": child.age_years,
            "meets": {},
            "shortages": {},
        }
        
        for nutrient, required in needs.items():
            actual = day_nutrition.get(nutrient, 0)
            meets = actual >= required * 0.8  # 80% threshold is acceptable
            assessment["meets"][nutrient] = meets
            if not meets:
                shortage = round(required - actual, 2)
                if shortage > 0:
                    assessment["shortages"][nutrient] = shortage
        
        assessments[child.id] = assessment
    
    return assessments