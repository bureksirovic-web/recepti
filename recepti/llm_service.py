"""
LLM Service — recipe suggestions via OpenRouter.
Free model: google/gemini-2.5-flash-preview
"""

import json
import logging
import os
import re
from typing import Any, Optional

from .models import Ingredient, RecipeTags, NutritionPerServing, Recipe

import requests

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
MODEL = "google/gemini-2.5-flash-preview"


def call_openrouter(
    prompt: str,
    model: str = None,
    temperature: float = None,
    max_tokens: int = None,
    **kwargs,
) -> str:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY environment variable not set")
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://recepti.bot",
        "X-Title": "Recepti Family Recipe Bot",
    }
    payload = {
        "messages": [{"role": "user", "content": prompt}],
    }
    if model is not None:
        payload["model"] = model
    elif MODEL:
        payload["model"] = MODEL
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    payload.update(kwargs)
    response = requests.post(
        f"{OPENROUTER_API_BASE}/chat/completions",
        headers=headers,
        json=payload,
        timeout=30,
    )
    if response.status_code != 200:
        logger.error(f"OpenRouter API error {response.status_code}: {response.text}")
        raise RuntimeError(f"OpenRouter API error: {response.status_code}")
    return response.json()["choices"][0]["message"]["content"].strip()


def suggest_recipe(
    available_ingredients: list[str],
    family_size: int = 9,
    meal_type: str = "lunch",
) -> dict[str, Any]:
    prompt = f"""You are a Croatian family recipe expert. Based on available ingredients,
suggest ONE authentic recipe for a family of {family_size} people.

Available ingredients: {', '.join(available_ingredients)}
Preferred meal type: {meal_type}

Reply ONLY with valid JSON (no markdown, no explanation):
{{
    "recipe_name": "...",
    "recipe_id": "new",
    "why_this_recipe": "...",
    "scaling_notes": "...",
    "ingredients": [{{"name": "...", "amount": "...", "unit": "..."}}]
}}

Choose Croatian, Italian, Mediterranean, or family-friendly cuisines.
Prefer recipes practical for a busy family with young children."""
    try:
        raw = call_openrouter(prompt)
        raw = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"^```\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw, flags=re.IGNORECASE)
        result = json.loads(raw)
        return {
            "recipe_name": result.get("recipe_name", "Unknown Recipe"),
            "recipe_id": "new",
            "why_this_recipe": result.get("why_this_recipe", ""),
            "scaling_notes": result.get("scaling_notes", ""),
            "ingredients": result.get("ingredients", []),
        }
    except Exception as e:
        logger.error(f"suggest_recipe failed: {e}")
        return {
            "recipe_name": "Suggestion unavailable",
            "recipe_id": "error",
            "why_this_recipe": str(e),
            "scaling_notes": "",
            "ingredients": [],
        }


def scale_ingredients_for_family(
    ingredients: list[dict[str, Any]],
    original_servings: int,
    target_servings: int,
) -> list[dict[str, Any]]:
    if original_servings <= 0 or target_servings <= 0:
        return ingredients
    ratio = target_servings / original_servings
    scaled = []
    for ing in ingredients:
        try:
            amount = float(ing.get("amount", "1").split()[0])
            scaled_amount = round(amount * ratio, 2)
        except (ValueError, IndexError):
            scaled_amount = ing.get("amount", "1")
        scaled.append({
            "name": ing["name"],
            "amount": str(scaled_amount),
            "unit": ing.get("unit", ""),
        })
    return scaled


def extract_recipe_from_url(
    url: str,
    page_content: str,
    croatia_hint: str,
    vegetarian_constraint: str = (
        "ONLY lacto-ovo vegetarian recipes. "
        "Reject any recipe containing: chicken, beef, pork, fish, salmon, tuna, "
        "tofu, tempeh, seitan, gelatin, bacon, ham, shrimp, sausage."
    ),
    max_tokens: int = 1500,
) -> Optional[Recipe]:
    """
    Extract structured recipe from a scraped web page using LLM.

    Args:
        url: Source URL (for attribution)
        page_content: Raw text extracted from the page
        croatia_hint: Hint about Croatia-available ingredients
        vegetarian_constraint: Text constraint for vegetarian-only extraction
        max_tokens: Max LLM response tokens

    Returns:
        Recipe object or None if extraction fails
    """
    prompt = (
        f"You are a recipe extraction expert. Extract the recipe from this web page.\n\n"
        f"SOURCE URL: {url}\n\n"
        f"CROATIA HINT: {croatia_hint}\n\n"
        f"DIETARY CONSTRAINT: {vegetarian_constraint}\n\n"
        "Extract ONLY lacto-ovo vegetarian recipes using ingredients available in Croatia.\n\n"
        "Reply with ONLY valid JSON (no markdown, no explanation):\n"
        '{\n'
        '  "name": "Recipe Name",\n'
        '  "description": "Brief 1-2 sentence description",\n'
        '  "ingredients": [\n'
        '    {"name": "ingredient name", "amount": "1", "unit": "cup"}\n'
        '  ],\n'
        '  "instructions": ["Step 1 description", "Step 2 description"],\n'
        '  "tags": {\n'
        '    "cuisine": "Cuisine type",\n'
        '    "meal_type": "breakfast|lunch|dinner|snack",\n'
        '    "dietary_tags": ["vegetarian"]\n'
        '  },\n'
        '  "servings": 4,\n'
        '  "prep_time_min": 15,\n'
        '  "cook_time_min": 30,\n'
        '  "difficulty": "easy|medium|hard"\n'
        '}\n\n'
        'If no valid vegetarian recipe is found, reply with ONLY:\n'
        '{"error": "No valid recipe found"}\n\n'
        "PAGE CONTENT:\n"
        + page_content[:6000]
    )

    response = call_openrouter(prompt, max_tokens=max_tokens)
    if not response:
        return None

    try:
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            logger.error("No JSON found in LLM response")
            return None
        json_str = response[json_start:json_end]
        data = json.loads(json_str)

        if "error" in data or not data.get("name"):
            logger.warning(f"LLM returned error or no name: {data.get('error', 'missing name')}")
            return None

        ingredients = [
            Ingredient(
                name=ing.get("name", ""),
                amount=str(ing.get("amount", "")),
                unit=ing.get("unit", ""),
            )
            for ing in data.get("ingredients", [])
            if ing.get("name")
        ]

        tags = RecipeTags(
            cuisine=data.get("tags", {}).get("cuisine", "International"),
            meal_type=data.get("tags", {}).get("meal_type", "lunch"),
            dietary_tags=data.get("tags", {}).get("dietary_tags", ["vegetarian"]),
        )

        instructions = data.get("instructions", [])
        if isinstance(instructions, str):
            instructions = [s.strip() for s in instructions.split(".") if s.strip()]

        recipe = Recipe(
            id=0,
            name=data.get("name", "Unknown Recipe"),
            description=data.get("description", ""),
            ingredients=ingredients,
            instructions=instructions,
            tags=tags,
            servings=data.get("servings", 4),
            prep_time_min=data.get("prep_time_min", 0),
            cook_time_min=data.get("cook_time_min", 0),
            nutrition_per_serving=NutritionPerServing(0, 0, 0, 0, 0, 0, 0, 0, 0),
            difficulty=data.get("difficulty", "medium"),
            source_url=url,
        )

        return recipe

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON: {e} — response: {response[:200]}")
        return None
    except Exception as e:
        logger.error(f"extract_recipe_from_url failed: {e}")
        return None


def parse_meal_description(
    text: str,
    family_members: list[str],
    known_recipes: list[str],
) -> dict:
    """
    Parse Croatian free-text meal description into structured JSON via LLM.
    Returns raw dict (parsed by meal_parser.py into dataclasses).
    """
    family_str = ", ".join(f'"{n}"' for n in family_members) if family_members else "(none)"
    recipes_str = ", ".join(f'"{n}"' for n in known_recipes) if known_recipes else "(none)"

    prompt = f"""You are parsing Croatian family meal descriptions.

TASK: Extract structured meal information from free-form Croatian text.
Return VALID JSON ONLY — no markdown, no explanation, no apology.

FAMILY MEMBERS (exact names): {family_str}
KNOWN RECIPES (partial names OK): {recipes_str}

CROATIAN MEAL TYPES:
- "doručak", "doručak", "za doručak" → breakfast
- "ručak", "za ručak" → lunch
- "večera", "večeru", "za večeru", "večeri" → dinner

USER INPUT: {text}

RESPONSE FORMAT (valid JSON only, no markdown):
{{
  "meals": [
    {{
      "meal_type": "breakfast|lunch|dinner",
      "recipe_name": "matched recipe name or unknown",
      "eaters": [
        {{
          "member_name": "matched member name",
          "amount": 0.0,
          "notes": ""
        }}
      ]
    }}
  ],
  "confidence": 0.85,
  "unmatched_members": ["UnknownName"],
  "unmatched_recipes": ["UnknownRecipe"]
}}

RULES:
- Parse amounts: "2 porcije" → 2.0, "pojeo" → 1.0, "nije jela" → 0.0
- "svi", "sve", "svi su" → all known family members
- "nitko", "ništa", "nije jela" → skip this meal
- If recipe name partially matches known_recipes, include in unmatched_recipes
- Confidence: 1.0 = all matched, 0.5 = partial, 0.0 = no meals found"""

    if not OPENROUTER_API_KEY:
        return {"meals": [], "confidence": 0.0, "unmatched_members": [], "unmatched_recipes": []}

    try:
        raw = call_openrouter(prompt)
        raw = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"^```\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw, flags=re.IGNORECASE)
        return json.loads(raw)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        logger.warning(f"parse_meal_description failed: {e}")
        return {"meals": [], "confidence": 0.0, "unmatched_members": [], "unmatched_recipes": []}


def translate_text(
    text: str,
    target_lang: str,
    source_lang: str = "en",
    glossary: list[str] = None,
) -> str:
    glossary_instruction = ""
    if glossary:
        glossary_instruction = (
            f"\n\nMUST preserve these terms exactly (do not translate them): "
            + ", ".join(f'"{term}"' for term in glossary)
        )

    prompt = f"""Translate the following text from {source_lang} to {target_lang}.
Use accurate food terminology for Croatian/Mediterranean cuisine.{glossary_instruction}

TEXT TO TRANSLATE:
{text}

Respond with ONLY the translated text, no explanations or notes."""

    return call_openrouter(
        prompt,
        model="google/gemma-4-26b-a4b-it:free",
        temperature=0.0,
        max_tokens=2048,
    )