"""Meal planning functionality for Recepti."""

import random
from datetime import date, timedelta
from typing import Any

from recepti.models import MealPlan, Recipe, RecipeCollection

# Meal slot types
BREAKFAST = "breakfast"
LUNCH = "lunch"
DINNER = "dinner"
MEAL_SLOTS = [BREAKFAST, LUNCH, DINNER]


def generate_weekly_plan(
    days: int = 7, preferences: dict[str, Any] | None = None
) -> dict[str, MealPlan]:
    """
    Generate a weekly meal plan.

    Args:
        days: Number of days to plan (default 7)
        preferences: Optional preferences dict with keys:
            - recipe_collection: RecipeCollection instance
            - excluded_ids: list of recipe IDs to avoid
            - preferred_slots: dict mapping meal slot to preferred cuisine/tags

    Returns dict of {date_str: MealPlan}
    """
    preferences = preferences or {}
    recipe_collection = preferences.get("recipe_collection")
    excluded_ids = set(preferences.get("excluded_ids", []))
    preferred_slots = preferences.get("preferred_slots", {})

    result = {}
    start_date = date.today()

    for i in range(days):
        plan_date = start_date + timedelta(days=i)
        date_str = plan_date.isoformat()

        breakfast_id = (
            _pick_recipe_for_slot(
                BREAKFAST, recipe_collection, excluded_ids, preferred_slots.get(BREAKFAST)
            )
            if recipe_collection
            else None
        )
        if breakfast_id:
            excluded_ids.add(breakfast_id)
        lunch_id = (
            _pick_recipe_for_slot(
                LUNCH, recipe_collection, excluded_ids, preferred_slots.get(LUNCH)
            )
            if recipe_collection
            else None
        )
        if lunch_id:
            excluded_ids.add(lunch_id)
        dinner_id = (
            _pick_recipe_for_slot(
                DINNER, recipe_collection, excluded_ids, preferred_slots.get(DINNER)
            )
            if recipe_collection
            else None
        )
        if dinner_id:
            excluded_ids.add(dinner_id)

        result[date_str] = MealPlan(
            date=plan_date,
            breakfast_id=breakfast_id,
            lunch_id=lunch_id,
            dinner_id=dinner_id,
        )

    return result


def _pick_recipe_for_slot(
    slot: str,
    collection: RecipeCollection | None,
    excluded_ids: set[int],
    preferred_tags: dict[str, str] | None = None,
) -> int | None:
    """Pick a recipe for a meal slot, avoiding repeats."""
    if collection is None:
        return None

    preferred_tags = preferred_tags or {}

    candidates = []
    for recipe in collection.recipes:
        if recipe.id in excluded_ids:
            continue
        if recipe.tags.meal_type and recipe.tags.meal_type != slot:
            # Also allow recipes tagged with multiple meal types
            if slot not in recipe.tags.meal_type.split(","):
                continue

        score = 0
        if preferred_tags:
            for key, value in preferred_tags.items():
                if getattr(recipe.tags, key, "") == value:
                    score += 1
        else:
            score = 1

        candidates.append((recipe, score))

    if not candidates:
        # Fallback: any recipe not in excluded AND compatible with slot
        for recipe in collection.recipes:
            if recipe.id in excluded_ids:
                continue
            # Allow if meal_type is empty (universal) or contains this slot
            mt = recipe.tags.meal_type
            if mt == "" or slot in mt.split(","):
                candidates.append((recipe, 0))

    if not candidates:
        return None

    # Sort by score descending, then random
    candidates.sort(key=lambda x: (x[1], random.random()), reverse=True)
    return candidates[0][0].id


def suggest_recipe_for_slot(
    slot: str,
    available_ingredients: list[str],
    already_planned: list[int],
) -> Recipe | None:
    """
    Suggest a recipe matching the meal slot and available ingredients.

    Args:
        slot: Meal slot ('breakfast', 'lunch', 'dinner')
        available_ingredients: List of ingredient names available
        already_planned: List of recipe IDs already planned this week

    Returns:
        A Recipe matching criteria, or None if no match found.
    """
    # This is a simplified stub - real implementation would use RecipeCollection
    # For now, return None to indicate no suggestion available
    return None


def get_meal_slot_name(slot: str) -> str:
    """Get human-readable name for a meal slot."""
    names = {
        BREAKFAST: "Breakfast",
        LUNCH: "Lunch",
        DINNER: "Dinner",
    }
    return names.get(slot, slot)


def format_meal_plan(date_str: str, plan: MealPlan) -> str:
    """Format a meal plan for display."""
    lines = [f"Meal Plan for {date_str}:", ""]

    if plan.breakfast_id:
        lines.append(f"  Breakfast: Recipe #{plan.breakfast_id}")
    else:
        lines.append("  Breakfast: (not planned)")

    if plan.lunch_id:
        lines.append(f"  Lunch: Recipe #{plan.lunch_id}")
    else:
        lines.append("  Lunch: (not planned)")

    if plan.dinner_id:
        lines.append(f"  Dinner: Recipe #{plan.dinner_id}")
    else:
        lines.append("  Dinner: (not planned)")

    if plan.notes:
        lines.append(f"  Notes: {plan.notes}")

    return "\n".join(lines)
