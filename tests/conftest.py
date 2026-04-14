"""Pytest configuration and fixtures for Recepti tests."""
import pytest
import json
import tempfile
from pathlib import Path

from recepti.models import (
    Ingredient, NutritionPerServing, RecipeTags,
    Recipe, Child,
)


@pytest.fixture
def sample_ingredients():
    return [
        Ingredient("rice", 200, "g"),
        Ingredient("toor_dal", 100, "g"),
        Ingredient("onion", 50, "g"),
        Ingredient("tomatoes", 100, "g"),
        Ingredient("cumin seeds", 5, "g"),
        Ingredient("turmeric", 2, "g"),
    ]


@pytest.fixture
def sample_tags():
    return RecipeTags(
        cuisine="Punjabi",
        meal_type="lunch",
        dietary_tags=["vegetarian", "lacto-ovo"],
    )


@pytest.fixture
def sample_recipe(sample_ingredients, sample_tags):
    return Recipe(
        id=1,
        name="Dal Tadka",
        description="Classic Punjabi dal with tempering",
        ingredients=sample_ingredients,
        instructions=[
            "Wash dal and pressure cook with turmeric.",
            "Heat oil, fry cumin and onion.",
            "Add tomatoes and cook.",
            "Pour tempering over dal.",
        ],
        tags=sample_tags,
        servings=4,
        prep_time_min=10,
        cook_time_min=25,
        nutrition_per_serving=NutritionPerServing(
            calories=180, protein_g=8, carbs_g=30, fat_g=4,
            fiber_g=6, iron_mg=3, calcium_mg=50, folate_mcg=100, b12_mcg=0,
        ),
        difficulty="easy",
    )


@pytest.fixture
def sample_recipes(sample_recipe):
    """A collection of 5 diverse recipes."""
    recipes = [sample_recipe]

    r2_ingredients = [
        Ingredient("paneer", 250, "g"),
        Ingredient("onion", 100, "g"),
        Ingredient("tomatoes", 150, "g"),
        Ingredient("garam masala", 5, "g"),
    ]
    r2_tags = RecipeTags(cuisine="Punjabi", meal_type="lunch,dinner", dietary_tags=["vegetarian"])
    recipes.append(Recipe(
        id=2, name="Paneer Butter Masala",
        description="Creamy tomato paneer curry",
        ingredients=r2_ingredients,
        instructions=["Cube paneer.", "Make tomato gravy.", "Add paneer to gravy."],
        tags=r2_tags, servings=3, prep_time_min=15, cook_time_min=30,
        nutrition_per_serving=NutritionPerServing(calories=320, protein_g=15, carbs_g=12, fat_g=25, fiber_g=2, iron_mg=2, calcium_mg=300, folate_mcg=20, b12_mcg=0.5),
        difficulty="medium",
    ))

    r3_tags = RecipeTags(cuisine="South Indian", meal_type="breakfast", dietary_tags=["vegetarian", "lacto-ovo"])
    r3_ingredients = [
        Ingredient("rice", 300, "g"),
        Ingredient("yogurt", 200, "g"),
        Ingredient("cucumber", 100, "g"),
    ]
    recipes.append(Recipe(
        id=3, name="Curd Rice",
        description="Cooling South Indian rice with yogurt",
        ingredients=r3_ingredients,
        instructions=["Cook rice.", "Mix with yogurt.", "Temper with mustard seeds."],
        tags=r3_tags, servings=2, prep_time_min=10, cook_time_min=20,
        nutrition_per_serving=NutritionPerServing(calories=250, protein_g=7, carbs_g=45, fat_g=5, fiber_g=1, iron_mg=1, calcium_mg=120, folate_mcg=15, b12_mcg=0.3),
        difficulty="easy",
    ))

    r4_tags = RecipeTags(cuisine="Gujarati", meal_type="lunch", dietary_tags=["vegetarian"])
    r4_ingredients = [
        Ingredient("roti", 100, "g"),
        Ingredient("vegetables", 200, "g"),
        Ingredient("yogurt", 100, "g"),
    ]
    recipes.append(Recipe(
        id=4, name="Kadhi",
        description="Gujarati yogurt curry",
        ingredients=r4_ingredients,
        instructions=["Make yogurt base.", "Add vegetables.", "Simmer."],
        tags=r4_tags, servings=4, prep_time_min=10, cook_time_min=30,
        nutrition_per_serving=NutritionPerServing(calories=150, protein_g=5, carbs_g=22, fat_g=4, fiber_g=3, iron_mg=2, calcium_mg=80, folate_mcg=40, b12_mcg=0.2),
        difficulty="medium",
    ))

    r5_tags = RecipeTags(cuisine="Bengali", meal_type="dinner", dietary_tags=["vegetarian", "lacto-ovo"])
    r5_ingredients = [
        Ingredient("rice", 200, "g"),
        Ingredient("masoor_dal", 100, "g"),
        Ingredient("spinach", 100, "g"),
    ]
    recipes.append(Recipe(
        id=5, name="Masoor Dal with Spinach",
        description="Bengali lentil and spinach dal",
        ingredients=r5_ingredients,
        instructions=["Pressure cook dal.", "Add spinach.", "Temper."],
        tags=r5_tags, servings=4, prep_time_min=10, cook_time_min=25,
        nutrition_per_serving=NutritionPerServing(calories=200, protein_g=10, carbs_g=38, fat_g=2, fiber_g=8, iron_mg=4, calcium_mg=100, folate_mcg=150, b12_mcg=0),
        difficulty="easy",
    ))

    # Extra breakfast and dinner recipes so planner has enough per slot
    r6_tags = RecipeTags(cuisine="North Indian", meal_type="breakfast", dietary_tags=["vegetarian", "lacto-ovo"])
    recipes.append(Recipe(
        id=6, name="Roti with Curd",
        description="Simple breakfast",
        ingredients=[Ingredient("roti", 150, "g"), Ingredient("yogurt", 150, "g")],
        instructions=["Warm roti.", "Serve with curd."],
        tags=r6_tags, servings=2, prep_time_min=5, cook_time_min=10,
        nutrition_per_serving=NutritionPerServing(calories=180, protein_g=6, carbs_g=30, fat_g=4, fiber_g=2, iron_mg=2, calcium_mg=100, folate_mcg=30, b12_mcg=0.3),
        difficulty="easy",
    ))

    r7_tags = RecipeTags(cuisine="South Indian", meal_type="dinner", dietary_tags=["vegetarian"])
    recipes.append(Recipe(
        id=7, name="Rice with Sambhar",
        description="South Indian dinner",
        ingredients=[Ingredient("rice", 300, "g"), Ingredient("sambhar", 200, "g")],
        instructions=["Cook rice.", "Serve with sambhar."],
        tags=r7_tags, servings=3, prep_time_min=10, cook_time_min=20,
        nutrition_per_serving=NutritionPerServing(calories=280, protein_g=8, carbs_g=55, fat_g=3, fiber_g=4, iron_mg=3, calcium_mg=60, folate_mcg=80, b12_mcg=0),
        difficulty="easy",
    ))

    return recipes


@pytest.fixture
def temp_recipes_file(sample_recipes):
    """Write sample recipes to a temp JSON file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        data = {
            "recipes": [
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "ingredients": [{"name": i.name, "amount": i.amount, "unit": i.unit} for i in r.ingredients],
                    "instructions": r.instructions,
                    "tags": {"cuisine": r.tags.cuisine, "meal_type": r.tags.meal_type, "dietary_tags": r.tags.dietary_tags},
                    "servings": r.servings,
                    "prep_time_min": r.prep_time_min,
                    "cook_time_min": r.cook_time_min,
                    "difficulty": r.difficulty,
                }
                for r in sample_recipes
            ]
        }
        json.dump(data, f)
        return Path(f.name)


@pytest.fixture
def sample_children():
    return [
        Child(id=1, name="Alice", age_years=5),
        Child(id=2, name="Bob", age_years=9),
        Child(id=3, name="Carol", age_years=12),
    ]