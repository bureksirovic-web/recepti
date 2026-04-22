"""Recipe expansion via web search and LLM extraction."""

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

import requests
from duckduckgo_search import DDGS
from lxml import html

from .models import Ingredient, Recipe, RecipeTags, NutritionPerServing
from .recipe_store import RecipeStore

logger = logging.getLogger(__name__)


@dataclass
class ExpansionResult:
    """Result of a recipe expansion attempt."""
    success: bool
    recipe: Optional[Recipe] = None
    source_url: str = ""
    error_message: str = ""
    was_duplicate: bool = False


class RecipeExpander:
    """
    Expands recipe database via web search and LLM extraction.

    Pipeline:
    1. Search DuckDuckGo for recipes with given ingredient
    2. Fetch top URLs and extract structured recipes via LLM
    3. Validate against Croatia ingredients and vegetarian constraints
    4. Deduplicate and save to expanded_recipes.json
    """

    def __init__(
        self,
        store: RecipeStore,
        croatia_ingredients_path: str = "data/croatia_ingredients.json",
        expanded_recipes_path: str = "data/expanded_recipes.json",
    ):
        self.store = store
        self.croatia_ingredients_path = croatia_ingredients_path
        self.expanded_recipes_path = expanded_recipes_path
        self._croatia_ingredients: set[str] = set()
        self._load_croatia_ingredients()

    def _load_croatia_ingredients(self) -> None:
        """Load Croatia ingredients whitelist into memory."""
        try:
            with open(self.croatia_ingredients_path, encoding="utf-8") as f:
                data = json.load(f)
            for category, ingredients in data.get("categories", {}).items():
                for ingredient in ingredients:
                    self._croatia_ingredients.add(ingredient.lower())
            logger.info(f"Loaded {len(self._croatia_ingredients)} Croatia ingredients")
        except Exception as e:
            logger.warning(f"Could not load Croatia ingredients: {e}")

    def _search_recipes(self, ingredient: str, max_results: int = 5) -> list[str]:
        """Search DuckDuckGo for recipe URLs."""
        search_query = f"vegetarian recipe with {ingredient}"
        urls = []
        try:
            with DDGS() as ddgs:
                for result in ddgs.text(search_query, max_results=max_results * 2):
                    url = result.get("href", "")
                    if url and url.startswith("http"):
                        urls.append(url)
        except Exception as e:
            logger.warning(f"Search failed for '{ingredient}': {e}")
        logger.info(f"Found {len(urls)} URLs for ingredient '{ingredient}'")
        return urls[:max_results * 2]

    def _fetch_page_content(self, url: str) -> Optional[str]:
        """Fetch and parse HTML content from URL."""
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            tree = html.fromstring(response.content)
            for tag in tree.cssselect("script, style, nav, header, footer, aside, form"):
                try:
                    tag.getparent().remove(tag)
                except Exception:
                    pass
            text = tree.text_content()
            return text[:8000]
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None

    def _check_ingredient_availability(
        self, ingredient_names: list[str]
    ) -> tuple[list[str], list[str]]:
        """Split ingredients into Croatia-available and unavailable."""
        available = []
        unavailable = []
        for name in ingredient_names:
            ing_lower = name.lower().strip()
            if ing_lower in self._croatia_ingredients:
                available.append(name)
            else:
                unavailable.append(name)
        return available, unavailable

    def _is_strictly_vegetarian(
        self, ingredient_names: list[str], instructions: list[str]
    ) -> bool:
        """Reject any recipe with meat, fish, poultry, or meat substitutes."""
        forbidden = [
            "chicken", "beef", "pork", "lamb", "turkey", "duck",
            "bacon", "ham", "sausage", "pepperoni", "salami", "prosciutto", "pancetta",
            "fish", "salmon", "tuna", "cod", "sardine", "anchovy", "shrimp",
            "prawn", "lobster", "crab", "scallop", "clam", "mussel", "oyster",
            "tofu", "tempeh", "seitan",
            "gelatin", "rennet", "isinglass",
        ]
        all_text = " ".join(ingredient_names + instructions).lower()
        for term in forbidden:
            if term in all_text:
                return False
        return True

    def _normalize_name(self, name: str) -> str:
        """Normalize recipe name for deduplication."""
        normalized = name.lower().strip()
        normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    def _is_duplicate(self, recipe_name: str) -> bool:
        """Check if similar recipe already exists in store."""
        norm = self._normalize_name(recipe_name)
        norm_words = set(norm.split())
        if len(norm_words) < 2:
            return False
        for recipe in self.store._recipes:
            recipe_norm = self._normalize_name(recipe.name)
            recipe_words = set(recipe_norm.split())
            overlap = norm_words & recipe_words
            if len(overlap) >= 2 and len(norm_words) >= 2:
                return True
        return False

    def expand_single_recipe(self, url: str, croatia_hint: str) -> ExpansionResult:
        """
        Expand a single recipe from URL.

        1. Fetch page content
        2. Extract structured recipe via LLM
        3. Validate vegetarian + Croatia constraints
        4. Deduplicate
        5. Save if valid
        """
        from .llm_service import extract_recipe_from_url

        content = self._fetch_page_content(url)
        if not content:
            return ExpansionResult(
                success=False, source_url=url,
                error_message="Failed to fetch page"
            )

        extracted = extract_recipe_from_url(url, content, croatia_hint)
        if not extracted:
            return ExpansionResult(
                success=False, source_url=url,
                error_message="LLM extraction failed"
            )

        ing_names = [i.name for i in extracted.ingredients]
        if not self._is_strictly_vegetarian(ing_names, extracted.instructions):
            return ExpansionResult(
                success=False, source_url=url,
                error_message="Contains non-vegetarian ingredients"
            )

        if self._is_duplicate(extracted.name):
            return ExpansionResult(
                success=False, source_url=url,
                was_duplicate=True,
                error_message="Duplicate recipe"
            )

        existing_ids = [r.id for r in self.store._recipes]
        new_id = max(existing_ids) + 1 if existing_ids else 51
        extracted.id = new_id

        try:
            with open(self.expanded_recipes_path, encoding="utf-8") as f:
                expanded_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            expanded_data = {"recipes": [], "version": 1}

        recipe_dict = {
            "id": extracted.id,
            "name": extracted.name,
            "description": extracted.description,
            "ingredients": [
                {"name": i.name, "amount": i.amount, "unit": i.unit}
                for i in extracted.ingredients
            ],
            "instructions": extracted.instructions,
            "tags": {
                "cuisine": extracted.tags.cuisine,
                "meal_type": extracted.tags.meal_type,
                "dietary_tags": extracted.tags.dietary_tags,
            },
            "servings": extracted.servings,
            "prep_time_min": extracted.prep_time_min,
            "cook_time_min": extracted.cook_time_min,
            "difficulty": extracted.difficulty,
            "source_url": extracted.source_url,
        }

        expanded_data["recipes"].append(recipe_dict)
        expanded_data["last_updated"] = datetime.now().isoformat()

        with open(self.expanded_recipes_path, "w", encoding="utf-8") as f:
            json.dump(expanded_data, f, indent=2, ensure_ascii=False)

        self.store._recipes.append(extracted)

        return ExpansionResult(
            success=True,
            recipe=extracted,
            source_url=url
        )

    def expand_ingredient(
        self, ingredient: str, max_recipes: int = 3
    ) -> list[ExpansionResult]:
        """
        Expand recipes for a given ingredient.

        Args:
            ingredient: Main ingredient to search for
            max_recipes: Maximum recipes to add

        Returns:
            List of ExpansionResults
        """
        croatia_hint = (
            "Use ONLY ingredients commonly available in Croatia. "
            f"Available: {', '.join(sorted(self._croatia_ingredients)[:80])}"
        )

        urls = self._search_recipes(ingredient, max_results=max_recipes * 2)
        results: list[ExpansionResult] = []

        for url in urls:
            if sum(1 for r in results if r.success) >= max_recipes:
                break
            result = self.expand_single_recipe(url, croatia_hint)
            results.append(result)
            if result.success:
                logger.info(f"✓ Added: {result.recipe.name}")
            elif result.was_duplicate:
                logger.info(f"⊘ Duplicate: {result.error_message}")
            else:
                logger.warning(f"✗ Failed: {result.error_message}")

        return results