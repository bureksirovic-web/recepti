"""Data models for Recepti meal planning application."""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Sex(Enum):
    MALE = "male"
    FEMALE = "female"


@dataclass
class Ingredient:
    """A single ingredient with amount and unit."""

    name: str
    amount: str  # str to handle "1/2", "3-4", "to taste", etc.
    unit: str


@dataclass
class NutritionPerServing:
    """Nutritional information per serving."""

    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    iron_mg: float
    calcium_mg: float
    folate_mcg: float
    b12_mcg: float


@dataclass
class RecipeTags:
    """Recipe categorization tags."""

    cuisine: str
    meal_type: str
    dietary_tags: list[str] = field(default_factory=list)


@dataclass
class Recipe:
    """A recipe with ingredients, instructions, and nutritional data."""

    id: int
    name: str
    description: str
    ingredients: list[Ingredient]
    instructions: list[str]
    tags: RecipeTags
    servings: int
    prep_time_min: int
    cook_time_min: int
    nutrition_per_serving: NutritionPerServing
    difficulty: str
    source_url: str = ""


@dataclass
class MealPlan:
    """A daily meal plan with breakfast, lunch, and dinner recipes."""

    date: date
    breakfast_id: int | None = None
    lunch_id: int | None = None
    dinner_id: int | None = None
    notes: str = ""


@dataclass
class Child:
    """A child with food preferences and restrictions."""

    id: int
    name: str
    age_years: float
    dislikes: list[str] = field(default_factory=list)
    favorites: list[int] = field(default_factory=list)


@dataclass
class DailyIntake:
    """A record of food intake for a child at a specific meal."""

    child_id: int
    date: date
    meal_type: str
    recipe_id: int
    amount_served: float
    amount_eaten: float


@dataclass
class RecipeCollection:
    """A collection of recipes with search functionality."""

    recipes: list[Recipe] = field(default_factory=list)

    def find_by_ingredients(self, search_ingredients: list[str]) -> list[tuple[Recipe, int]]:
        """
        Find recipes matching search ingredients, scored by match count.

        Returns list of (Recipe, match_count) tuples sorted by match_count descending.
        Only recipes with at least one match are returned.
        """
        scored: list[tuple[Recipe, int]] = []
        search_lower = [ing.lower() for ing in search_ingredients]

        for recipe in self.recipes:
            match_count = sum(
                1
                for ing in recipe.ingredients
                if any(search in ing.name.lower() for search in search_lower)
            )
            if match_count > 0:
                scored.append((recipe, match_count))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def find_by_tags(self, tags: RecipeTags) -> list[Recipe]:
        """Find recipes matching the given tags."""
        results: list[Recipe] = []
        for recipe in self.recipes:
            if (recipe.tags.cuisine == tags.cuisine or tags.cuisine == "") and (
                recipe.tags.meal_type == tags.meal_type or tags.meal_type == ""
            ):
                results.append(recipe)
        return results


@dataclass
class FamilyMember:
    """A family member with nutrient targets based on WHO/FAO/EFSA RDA."""

    id: int
    name: str
    sex: str
    age_years: float
    pregnant: bool = False
    lactating: bool = False
    dislikes: list[str] = field(default_factory=list)

    @property
    def life_stage(self) -> str:
        age = self.age_years
        if age < 1:
            return "infant"
        if age < 4:
            return "toddler"
        if age < 10:
            return "child"
        if age < 18:
            return "adolescent"
        return "adult"


@dataclass
class CookingSession:
    """A cooking session shared by the whole family."""

    id: int
    date: date
    recipe_id: int
    servings_made: float
    servings_served: dict[int, float] = field(default_factory=dict)
    notes: str = ""


@dataclass
class MemberNutritionSummary:
    """Aggregated nutrient intake for one member over a time window."""

    member_id: int
    member_name: str
    rda: dict[str, float]
    intake: dict[str, float]

    def pct_of_rda(self, nutrient: str) -> float:
        target = self.rda.get(nutrient, 1)
        return round(self.intake.get(nutrient, 0) / target * 100, 1)

    def gap(self, nutrient: str) -> float:
        return max(0.0, round(self.rda.get(nutrient, 0) - self.intake.get(nutrient, 0), 2))
