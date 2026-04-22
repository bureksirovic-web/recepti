"""Grocery availability filters for the Recepti app."""


def is_ingredient_available(ingredient_name: str, grocery_data: dict) -> bool:
    """
    Check if an ingredient is available in Croatian supermarkets.

    Args:
        ingredient_name: English or Croatian ingredient name (case-insensitive)
        grocery_data: Loaded grocery_availability.json dict
    Returns:
        True if available, False if not
    """
    if not grocery_data or "ingredients" not in grocery_data:
        return True

    name_lower = ingredient_name.lower()
    for entry in grocery_data["ingredients"]:
        if entry.get("name", "").lower() == name_lower or entry.get("croatian_name", "").lower() == name_lower:
            return entry.get("available", True)
    return True


def filter_recipes_by_grocery(recipes: list[dict], grocery_data: dict) -> list[dict]:
    """
    Filter out recipes that contain any unavailable ingredients.

    Args:
        recipes: List of recipe dicts (each has 'ingredients': [{'name': str}])
        grocery_data: Loaded grocery_availability.json dict
    Returns:
        Filtered list — recipes with ALL available ingredients
    """
    filtered = []
    for recipe in recipes:
        ingredients = recipe.get("ingredients", [])
        if all(is_ingredient_available(ing.get("name", ""), grocery_data) for ing in ingredients):
            filtered.append(recipe)
    return filtered