import difflib
import json
import re
import unicodedata
from dataclasses import dataclass

from recepti.llm_service import call_openrouter

KEYWORD_PRECHECK = [
    "ručak",
    "doručak",
    "doručak",
    "večeru",
    "večera",
    "večeri",
    "jeli",
    "jela",
    "jelo",
    "pojeo",
    "pojela",
    "pojelo",
    "kuhala",
    "kuhao",
    "kuhali",
    "servirala",
    "servirali",
    "porcija",
    "porcije",
    "servirano",
    "jelo",
]

SYSTEM_PROMPT = """You are parsing Croatian family meal descriptions.

TASK: Extract structured meal information from free-form Croatian text.
Return VALID JSON ONLY — no markdown, no explanation, no apology.

FAMILY MEMBERS (exact names): {family_members_str}
KNOWN RECIPES (partial names OK): {known_recipes_str}

CROATIAN MEAL TYPES:
- "doručak", "doručak", "za doručak" → breakfast
- "ručak", "za ručak" → lunch
- "večera", "večeru", "za večeru", "večeri" → dinner

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


@dataclass
class EaterEntry:
    member_name: str
    amount: float
    notes: str = ""


@dataclass
class ParsedMeal:
    meal_type: str
    recipe_name: str
    eaters: list[EaterEntry]
    notes: str = ""


@dataclass
class MealParsingResult:
    meals: list[ParsedMeal]
    confidence: float
    unmatched_members: list[str]
    unmatched_recipes: list[str]


def _normalize_for_comparison(text: str) -> str:
    text = text.lower().strip()
    normalized = ""
    for char in text:
        if unicodedata.category(char).startswith("Lo"):
            normalized += unicodedata.normalize("NFD", char)[0]
        else:
            normalized += char
    return normalized


def _fuzzy_match_member(input_name: str, family_members: list[str], threshold: float = 0.7) -> str | None:
    input_normalized = _normalize_for_comparison(input_name)
    best_match = None
    best_ratio = 0.0

    for member in family_members:
        member_normalized = _normalize_for_comparison(member)
        ratio = difflib.SequenceMatcher(None, input_normalized, member_normalized).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = member

    if best_ratio >= threshold:
        return best_match
    return None


def _fuzzy_match_recipe(input_name: str, known_recipes: list[str]) -> tuple[str | None, float]:
    if not known_recipes:
        return None, 0.0

    best_match = None
    best_ratio = 0.0

    for recipe in known_recipes:
        ratio = difflib.SequenceMatcher(None, input_name.lower(), recipe.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = recipe

    if best_ratio > 0.6:
        return best_match, best_ratio
    if 0.5 <= best_ratio <= 0.6:
        return best_match, best_ratio
    return None, best_ratio


def _parse_amount(text: str) -> float:
    text_lower = text.lower()

    if any(phrase in text_lower for phrase in ["nije jela", "ništa", "nitko", "ništa nije"]):
        return 0.0

    if re.search(r"(\d+(?:\.\d+)?)\s*porcije?", text_lower):
        match = re.search(r"(\d+(?:\.\d+)?)\s*porcije?", text_lower)
        if match:
            return float(match.group(1))

    if re.search(r"pola porcije", text_lower):
        return 0.5
    if re.search(r"jednu?\s*porcija", text_lower):
        return 1.0
    if re.search(r"punu?\s*porcija", text_lower):
        return 1.0
    if re.search(r"(pojeo|pojela|pojelo|\bjela\b|\bjelo\b)", text_lower):
        return 1.0

    return 1.0


def _has_meal_keywords(text: str) -> bool:
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in KEYWORD_PRECHECK)


def _call_llm_parser(text: str, family_members: list[str], known_recipes: list[str]) -> dict:
    family_members_str = ", ".join(family_members) if family_members else "(none)"
    known_recipes_str = ", ".join(known_recipes) if known_recipes else "(none)"

    user_prompt = f"""{SYSTEM_PROMPT.format(
        family_members_str=family_members_str,
        known_recipes_str=known_recipes_str,
    )}

USER TEXT TO PARSE:
{text}"""

    try:
        response = call_openrouter(user_prompt)
        return json.loads(response)
    except (json.JSONDecodeError, Exception):
        return {}


def parse_meal_description(
    text: str,
    family_members: list[str],
    known_recipes: list[str],
    llm_enabled: bool = True,
) -> MealParsingResult:
    if not text or not text.strip():
        return MealParsingResult(meals=[], confidence=0.0, unmatched_members=[], unmatched_recipes=[])

    if not _has_meal_keywords(text):
        return MealParsingResult(meals=[], confidence=0.0, unmatched_members=[], unmatched_recipes=[])

    if not llm_enabled:
        return MealParsingResult(meals=[], confidence=0.0, unmatched_members=[], unmatched_recipes=[])

    llm_result = _call_llm_parser(text, family_members, known_recipes)

    if not llm_result or "meals" not in llm_result:
        return MealParsingResult(meals=[], confidence=0.0, unmatched_members=[], unmatched_recipes=[])

    meals: list[ParsedMeal] = []
    unmatched_members: list[str] = llm_result.get("unmatched_members", [])
    unmatched_recipes: list[str] = llm_result.get("unmatched_recipes", [])
    confidence = llm_result.get("confidence", 0.0)

    for meal_data in llm_result.get("meals", []):
        meal_type = meal_data.get("meal_type", "unknown")
        recipe_name = meal_data.get("recipe_name", "unknown")
        eaters_data = meal_data.get("eaters", [])

        eaters: list[EaterEntry] = []
        for eater in eaters_data:
            member_name = eater.get("member_name", "")
            amount = eater.get("amount", 1.0)
            notes = eater.get("notes", "")

            matched = _fuzzy_match_member(member_name, family_members, threshold=0.7)
            if matched:
                eaters.append(EaterEntry(member_name=matched, amount=amount, notes=notes))
            else:
                unmatched_members.append(member_name)

        if recipe_name != "unknown" and recipe_name:
            matched_recipe, ratio = _fuzzy_match_recipe(recipe_name, known_recipes)
            if matched_recipe:
                recipe_name = matched_recipe
            elif ratio >= 0.5:
                unmatched_recipes.append(recipe_name)

        meals.append(ParsedMeal(meal_type=meal_type, recipe_name=recipe_name, eaters=eaters))

    return MealParsingResult(
        meals=meals,
        confidence=confidence,
        unmatched_members=unmatched_members,
        unmatched_recipes=unmatched_recipes,
    )