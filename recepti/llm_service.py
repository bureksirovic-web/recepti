"""
LLM Service — recipe suggestions via OpenRouter.
Free model: google/gemini-2.5-flash-preview
"""

import json
import logging
import os
import re
from typing import Any

import requests

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
MODEL = "google/gemini-2.5-flash-preview"


def call_openrouter(prompt: str) -> str:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY environment variable not set")
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://recepti.bot",
        "X-Title": "Recepti Family Recipe Bot",
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1024,
    }
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