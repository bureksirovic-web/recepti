"""
Web scraper for recipe sites — collects recipes from public Indian veg recipe pages.
Only imports what the user explicitly requests. No AI involvement.
"""

import json
import re
import ssl
import urllib.request
from typing import Any
from urllib.parse import urljoin

# ── SSL context ─────────────────────────────────────────────────────────
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


# ── HTTP helpers ─────────────────────────────────────────────────────
def fetch(url: str, timeout: int = 30) -> str:
    """Fetch a URL, return HTML/text."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ReceptiBot/1.0)"},
        method="GET",
    )
    with urllib.request.urlopen(req, context=_ctx, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_links(html: str, base: str) -> list[str]:
    """Extract recipe links from an index page."""
    links: set[str] = set()
    # Pattern for recipe links (adjust per site)
    for href in re.findall(r'href="([^"]*recipe[^"]*)"', html, re.IGNORECASE):
        links.add(urljoin(base, href))
    for href in re.findall(r"href='([^']*recipe[^']*)'", html, re.IGNORECASE):
        links.add(urljoin(base, href))
    return list(links)


# ── JSONLd extractor ──────────────────────────────────────────────────
def extract_jsonld(html: str) -> list[dict[str, Any]]:
    """Extract JSON-LD structured data (Schema.org Recipe)."""
    results: list[dict[str, Any]] = []
    for match in re.finditer(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL
    ):
        try:
            data = json.loads(match.group(1))
            if isinstance(data, list):
                for item in data:
                    if item.get("@type") == "Recipe":
                        results.append(item)
            elif data.get("@type") == "Recipe":
                results.append(data)
        except json.JSONDecodeError:
            pass
    return results


# ── Basic Recipe parser ──────────────────────────────────────────────────
def parse_jsonld_recipe(ld: dict[str, Any]) -> dict[str, Any]:
    """Convert a JSON-LD Recipe dict to our Recipe schema."""

    def _ingredients() -> list[dict[str, str]]:
        items = []
        for ing in ld.get("recipeIngredient", []):
            # Format: "2 cups flour" — try to split amount/unit/name
            parts = str(ing).strip().split(None, 2)
            if len(parts) == 1:
                items.append({"name": parts[0], "amount": "1", "unit": "piece"})
            elif len(parts) == 2:
                items.append({"name": parts[1], "amount": parts[0], "unit": "unit"})
            else:
                items.append({"name": parts[2], "amount": parts[0], "unit": parts[1]})
        return items

    def _instructions() -> list[str]:
        steps = []
        for step in ld.get("recipeInstructions", []):
            if isinstance(step, str):
                steps.append(step)
            elif isinstance(step, dict):
                text = step.get("text", "")
                if text:
                    steps.append(text)
        return steps

    def _tags() -> dict[str, Any]:
        cuisine = ld.get("recipeCuisine", "")
        meal_type = ld.get("recipeCategory", "")
        dietary: list[str] = []
        for tag in ld.get("suitableForDiet", []):
            # Schema.org URIs like https://schema.org/VegetarianDiet
            tag_name = re.sub(r".+#", "", tag)
            dietary.append(tag_name)
        return {"cuisine": cuisine, "meal_type": meal_type, "dietary_tags": dietary}

    return {
        "name": ld.get("name", "Unknown"),
        "description": ld.get("description", ""),
        "ingredients": _ingredients(),
        "instructions": _instructions(),
        "tags": _tags(),
        "servings": _parse_servings(ld.get("recipeYield", 1)),
        "prep_time_min": _parse_duration(ld.get("prepTime", "")),
        "cook_time_min": _parse_duration(ld.get("cookTime", "")),
        "difficulty": "medium",
    }


def _parse_servings(raw: Any, default: int = 1) -> int:
    """Extract integer servings from various formats."""
    if isinstance(raw, int):
        return raw
    s = str(raw).strip()
    m = re.search(r"\d+", s)
    return int(m.group()) if m else default


def _parse_duration(raw: str) -> int:
    """Parse ISO 8601 duration to minutes. PT30M → 30."""
    if not raw:
        return 0
    m = re.search(r"PT(?:(\d+)H)?(?:(\d+)M)?", str(raw))
    if not m:
        return 0
    hours = int(m.group(1)) if m.group(1) else 0
    mins = int(m.group(2)) if m.group(2) else 0
    return hours * 60 + mins


# ── Public recipe sites ──────────────────────────────────────────────
# Add sites here as they're discovered
KNOWN_SITES: list[tuple[str, str]] = [
    # (index_url, name)
]


def add_site(index_url: str, name: str = "") -> None:
    """Register a new recipe site."""
    if not name:
        name = index_url
    KNOWN_SITES.append((index_url, name))
