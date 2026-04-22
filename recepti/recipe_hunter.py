"""
Autonomous recipe hunter daemon for Recepti.

Scans coverage gaps, searches DuckDuckGo for Croatian vegetarian recipes,
extracts via LLM, deduplicates, and saves to the recipe store.
"""

import json
import logging
import os
import re
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests
from duckduckgo_search import DDGS
from lxml import html

from .models import Recipe, RecipeTags, Ingredient, NutritionPerServing
from .scraper import fetch, extract_jsonld, parse_jsonld_recipe
from .recipe_store import RecipeStore
from .llm_service import call_openrouter, extract_recipe_from_url

logger = logging.getLogger(__name__)

HUNT_INTERVAL_HOURS = int(os.getenv("RECEPTI_HUNT_INTERVAL_HOURS", "24"))
HUNT_STATE_FILE = os.getenv("RECEPTI_DATA_DIR", "data") + "/hunt_state.json"

# ── Coverage helpers (EXACT COPY from recepti/web_app.py) ──────────────────────────

_CUISINE_TERMS: dict[str, list[str]] = {
    "croatian": ["hrvatski recepti", "hrvatska kuhinja", "domaći recepti", "recepti po hrvatski"],
    "zagorje": ["zagorski recepti", "zagorje", "zagorska kuhinja"],
    "dalmatian": ["dalmatinski recepti", "dalmacija", "dalmatinska jela"],
    "istrian": ["istarski recepti", "istarska kuhinja", "istria"],
    "slavonian": ["slavonski recepti", "slavonija", "slavonska kuhinja"],
    "mediterranean": ["mediteranski recepti", "mediteranska kuhinja"],
    "punjabi": ["punjabi recepti"],
}

_MEAL_TERMS: dict[str, list[str]] = {
    "breakfast": ["recepti za doručak", "brzi doručak", "doručak bez jaja"],
    "lunch": ["recepti za ručak"],
    "dinner": ["recepti za večeru"],
    "snack": ["recepti za užinu", "zdrave užine", "brzi recepti za užinu"],
    "dessert": ["deserti", "recepti za desert", "slatki recepti"],
}

_DIFFICULTY_TERMS: dict[str, list[str]] = {
    "easy": ["jednostavni recepti", "lagani recepti"],
    "medium": ["srednje teški recepti"],
    "hard": ["zahtjevni recepti"],
}


def _suggest_queries(dimension: str, value: str) -> list[str]:
    value_lower = value.lower()
    if dimension == "cuisine":
        terms = _CUISINE_TERMS.get(value_lower, [f"{value_lower} recepti"])
        return terms + [f"{value} recipes croatia"]
    if dimension == "meal_type":
        terms = _MEAL_TERMS.get(value_lower, [f"recepti za {value_lower}"])
        return terms + [f"{value} recipes vegetarian"]
    if dimension == "difficulty":
        terms = _DIFFICULTY_TERMS.get(value_lower, [f"{value_lower} recepti"])
        return terms
    return [f"{value} recepti"]


def _build_reason(hole_type: str, dimension: str, value: str, rej_count: int) -> str:
    if hole_type == "coverage":
        return f"SPARSE coverage: {dimension}={value}"
    if hole_type == "rejection":
        return f"REJECTED cuisine: {value}"
    return f"BOTH: sparse {dimension}={value} AND rejections"


def _get_tag_val(r, dim: str) -> str:
    t = r.tags
    if dim == "cuisine":
        return t.cuisine
    if dim == "meal_type":
        return t.meal_type
    if dim == "difficulty":
        return r.difficulty
    return ""


def _build_holes(all_recipes, total: int) -> list[dict]:
    if total == 0:
        return []

    def _counts(dim: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in all_recipes:
            val = _get_tag_val(r, dim).lower()
            counts[val] = counts.get(val, 0) + 1
        return counts

    holes: list[dict] = []
    for dim in ["cuisine", "meal_type", "difficulty"]:
        for val, count in _counts(dim).items():
            if count < 3:
                priority = 99.0 if count == 0 else round(count / total, 4)
                status = "EMPTY" if count == 0 else "SPARSE"
                holes.append(
                    {
                        "dimension": dim,
                        "value": val,
                        "count": count,
                        "score": round(count / total, 4),
                        "priority": priority,
                        "status": status,
                        "suggested_queries": _suggest_queries(dim, val),
                    }
                )
    holes.sort(key=lambda h: h["priority"], reverse=True)
    return holes


# ── RecipeHunter ────────────────────────────────────────────────────────────────

class RecipeHunter:
    """
    Autonomous daemon that hunts for new Croatian vegetarian recipes.

    Each cycle:
    1. Build targets from coverage gaps + rejected cuisines
    2. Search DuckDuckGo for each target query on Croatian recipe sites
    3. Extract recipes via LLM (fallback JSON-LD if no API key)
    4. Deduplicate and validate
    5. Save new recipes to RecipeStore
    6. Sync cuisine rejections to CuisineBlacklister
    7. Notify HuntNotificationStore
    """

    def __init__(
        self,
        recipe_store: RecipeStore,
        cooking_log,  # CookingLogStore (injected to avoid circular import)
        ratings,  # RecipeRatingStore
        balancer,  # FamilyNutrientBalancer
        notification_store,  # HuntNotificationStore
        state_file: str = HUNT_STATE_FILE,
    ):
        self.recipe_store = recipe_store
        self.cooking_log = cooking_log
        self.ratings = ratings
        self.balancer = balancer
        self.notification_store = notification_store
        self.state_file = Path(state_file)
        self._next_recipe_id = (
            max(r.id for r in recipe_store._recipes) + 1 if recipe_store._recipes else 1
        )
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()

    # ── Lifecycle ───────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the hunter daemon thread."""
        self._running = True
        self._thread = threading.Thread(target=self._daemon_loop, daemon=True)
        self._thread.start()
        logger.info(f"RecipeHunter started — interval={HUNT_INTERVAL_HOURS}h")

    def stop(self) -> None:
        """Stop the hunter daemon thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("RecipeHunter stopped")

    # ── State persistence ───────────────────────────────────────────────────

    def _should_run(self) -> bool:
        """True if enough hours have passed since last hunt run."""
        with self._lock:
            try:
                with open(self.state_file, encoding="utf-8") as f:
                    data = json.load(f)
                last_run = datetime.fromisoformat(data["last_hunt_date"])
                hours_since = (datetime.now() - last_run).total_seconds() / 3600
                return hours_since >= HUNT_INTERVAL_HOURS
            except (FileNotFoundError, KeyError, ValueError):
                return True

    def _save_state(
        self, last_run: datetime, added: int, cycles: int, blacklisted: int
    ) -> None:
        """Persist hunt state to state file."""
        with self._lock:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(
                dir=str(self.state_file.parent), prefix=".tmp_", text=True
            )
            data = {
                "last_hunt_date": last_run.isoformat(),
                "recipes_added_this_cycle": added,
                "cycles_completed": cycles,
                "cuisines_blacklisted_this_cycle": blacklisted,
            }
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, self.state_file)
            except Exception:
                if os.path.exists(tmp):
                    os.unlink(tmp)
                raise

    def _load_state(self) -> dict:
        """Load hunt state, return empty dict if missing."""
        with self._lock:
            try:
                with open(self.state_file, encoding="utf-8") as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return {}

    def _cycles_completed(self) -> int:
        state = self._load_state()
        return state.get("cycles_completed", 0)

    # ── Targets ─────────────────────────────────────────────────────────────

    def _get_targets(self) -> list[dict]:
        """
        Build hunt targets from local coverage gap analysis + rejection signals.

        Mirrors /api/scrape-todo from web_app.py but without HTTP dependencies.
        """
        all_recipes = self.recipe_store._recipes
        total = len(all_recipes)
        if total == 0:
            return []

        coverage_holes = _build_holes(all_recipes, total)

        rejected_cuisines: dict[str, int] = {}
        try:
            rejected_cuisines = self.ratings.get_rejected_cuisines(
                self.recipe_store, threshold=2
            )
        except Exception as exc:
            logger.warning("Ratings store unavailable for targets: %s", exc)

        targets: list[dict] = []
        seen_queries: set[str] = set()

        # From coverage holes
        for hole in coverage_holes:
            dim = hole["dimension"]
            val = hole["value"]
            priority = hole["priority"]
            hole_type = "coverage"

            rej_count = rejected_cuisines.get(val, 0)
            if dim == "cuisine" and rej_count >= 2:
                priority = round(priority * (1 + 0.5), 4)
                hole_type = "both"

            queries = hole["suggested_queries"]
            for q in queries:
                if q.lower() not in seen_queries:
                    targets.append(
                        {
                            "query": q,
                            "reason": _build_reason(hole_type, dim, val, rej_count),
                            "priority_score": priority,
                            "type": hole_type,
                        }
                    )
                    seen_queries.add(q.lower())

        # From rejected cuisines
        for cuisine, rej_cnt in rejected_cuisines.items():
            mult = 0.5 if rej_cnt <= 3 else 1.0
            cuisine_lower = cuisine.lower()
            cuisine_queries = _suggest_queries("cuisine", cuisine_lower)
            for q in cuisine_queries:
                if q.lower() not in seen_queries:
                    targets.append(
                        {
                            "query": q,
                            "reason": (
                                f"REJECTED cuisine: {rej_cnt} members gave thumbs-down "
                                f"on {cuisine}"
                            ),
                            "priority_score": round(0.5 * (1 + mult), 4),
                            "type": "rejection",
                        }
                    )
                    seen_queries.add(q.lower())

        targets.sort(key=lambda t: t["priority_score"], reverse=True)
        return targets[:20]

    # ── DuckDuckGo search ────────────────────────────────────────────────────

    def _search_urls(self, query: str, max_results: int = 5) -> list[str]:
        """
        Search DuckDuckGo for recipe URLs matching query.

        Targets Croatian recipe sites. Falls back to general search without site:
        filter if all targeted searches fail.
        """
        urls: list[str] = []
        site_queries = [
            (f'{query} site:coolinarika.com', "coolinarika.com"),
            (f'{query} site:kuhaj.ba', "kuhaj.ba"),
            (f'{query} site:gastro.hr', "gastro.hr"),
            (f'{query} site:coolinarika.hr', "coolinarika.hr"),
        ]

        for sq, _ in site_queries:
            try:
                with DDGS() as ddgs:
                    for result in ddgs.text(sq, max_results=max_results):
                        href = result.get("href", "")
                        if href and href.startswith("http"):
                            urls.append(href)
            except Exception as exc:
                logger.warning("DDG site search failed for %s: %s", sq[:60], exc)

        # Fallback: general search if no results
        if not urls:
            logger.info("No results with site: filter — trying general search")
            try:
                with DDGS() as ddgs:
                    for result in ddgs.text(query, max_results=max_results * 2):
                        href = result.get("href", "")
                        if href and href.startswith("http"):
                            urls.append(href)
            except Exception as exc:
                logger.warning("DDG general search failed for %s: %s", query[:60], exc)

        return urls

    # ── Page fetch & extract ─────────────────────────────────────────────────

    def _fetch_page_content(self, url: str) -> Optional[str]:
        """Fetch HTML page and return text content."""
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            tree = html.fromstring(response.content)
            for tag in tree.cssselect("script, style, nav, header, footer, aside, form"):
                try:
                    tag.getparent().remove(tag)
                except Exception:
                    pass
            text = tree.text_content()
            return text[:8000]
        except Exception as exc:
            logger.warning("Failed to fetch page %s: %s", url, exc)
            return None

    def _extract_fallback_jsonld(self, url: str) -> Optional[Recipe]:
        """Fallback: try JSON-LD extraction when LLM key unavailable."""
        try:
            html_content = fetch(url, timeout=20)
            ld_entries = extract_jsonld(html_content)
            for ld in ld_entries:
                recipe_data = parse_jsonld_recipe(ld)
                if recipe_data.get("name") and recipe_data.get("ingredients"):
                    ingredients = [
                        Ingredient(
                            name=ing.get("name", ""),
                            amount=str(ing.get("amount", "")),
                            unit=ing.get("unit", ""),
                        )
                        for ing in recipe_data.get("ingredients", [])
                        if ing.get("name")
                    ]
                    tags_dict = recipe_data.get("tags", {})
                    tags = RecipeTags(
                        cuisine=tags_dict.get("cuisine", "International"),
                        meal_type=tags_dict.get("meal_type", "lunch"),
                        dietary_tags=tags_dict.get("dietary_tags", ["vegetarian"]),
                    )
                    instructions = recipe_data.get("instructions", [])
                    if isinstance(instructions, str):
                        instructions = [s.strip() for s in instructions.split(".") if s.strip()]
                    recipe = Recipe(
                        id=0,
                        name=recipe_data.get("name", "Unknown Recipe"),
                        description=recipe_data.get("description", ""),
                        ingredients=ingredients,
                        instructions=instructions,
                        tags=tags,
                        servings=recipe_data.get("servings", 4),
                        prep_time_min=recipe_data.get("prep_time_min", 0),
                        cook_time_min=recipe_data.get("cook_time_min", 0),
                        nutrition_per_serving=NutritionPerServing(
                            0, 0, 0, 0, 0, 0, 0, 0, 0
                        ),
                        difficulty=recipe_data.get("difficulty", "medium"),
                        source_url=url,
                    )
                    return recipe
        except Exception as exc:
            logger.warning("JSON-LD fallback extraction failed for %s: %s", url, exc)
        return None

    # ── Deduplication ────────────────────────────────────────────────────────────

    def _normalize_name(self, name: str) -> str:
        """Normalize recipe name for deduplication."""
        normalized = name.lower().strip()
        normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    def _is_duplicate(self, name: str) -> bool:
        """Check if recipe with same normalized name already exists."""
        norm = self._normalize_name(name)
        for recipe in self.recipe_store._recipes:
            if self._normalize_name(recipe.name) == norm:
                return True
        return False

    def _is_vegetarian_ish(
        self, ingredient_names: list[str], instructions: list[str]
    ) -> bool:
        """Reject recipes with obvious non-vegetarian ingredients."""
        forbidden = [
            "chicken", "beef", "pork", "lamb", "turkey", "duck",
            "bacon", "ham", "sausage", "pepperoni", "salami", "prosciutto", "pancetta",
            "fish", "salmon", "tuna", "cod", "sardine", "anchovy", "anchovies", "shrimp",
            "prawn", "lobster", "crab", "scallop", "clam", "mussel", "oyster",
            "tofu", "tempeh", "seitan",
            "gelatin", "rennet", "isinglass",
        ]
        all_text = " ".join(ingredient_names + instructions).lower()
        return not any(term in all_text for term in forbidden)

    # ── Extract and save ────────────────────────────────────────────────────

    def _extract_and_save(self, url: str) -> tuple[bool, str]:
        """
        Fetch URL, extract recipe, validate, and save if new.

        Returns (success, message).
        Uses LLM extraction if OPENROUTER_API_KEY is set,
        otherwise falls back to JSON-LD.
        """
        content = self._fetch_page_content(url)
        if not content:
            return False, "Failed to fetch page"

        recipe: Optional[Recipe] = None
        use_llm = bool(os.getenv("OPENROUTER_API_KEY", ""))

        if use_llm:
            try:
                croatia_hint = (
                    "Use ONLY ingredients commonly available in Croatia. "
                    "Available Staples: lentils, red lentils, green lentils, "
                    "chickpeas, white beans, mushrooms, spinach, potatoes, "
                    "tomatoes, rice, pasta, zucchini, cauliflower, eggplant, "
                    "bell pepper, carrots, cabbage, onions, garlic."
                )
                recipe = extract_recipe_from_url(
                    url=url,
                    page_content=content,
                    croatia_hint=croatia_hint,
                )
            except Exception as exc:
                logger.warning("LLM extraction failed for %s, falling back: %s", url, exc)
                recipe = None

        # Fallback to JSON-LD if LLM failed or key unavailable
        if recipe is None:
            logger.info("Attempting JSON-LD fallback for %s", url)
            recipe = self._extract_fallback_jsonld(url)

        if recipe is None:
            return False, "No recipe extracted"

        # Validate
        if recipe.name in ("No valid recipe found", "", "Unknown Recipe") or not recipe.name:
            return False, "Invalid recipe name"

        if len(recipe.ingredients) < 2:
            return False, f"Too few ingredients ({len(recipe.ingredients)})"

        if not recipe.instructions or len(recipe.instructions) < 1:
            return False, "No instruction steps"

        if self._is_duplicate(recipe.name):
            return False, "Duplicate recipe"

        if not self._is_vegetarian_ish(
            [i.name for i in recipe.ingredients], recipe.instructions
        ):
            return False, "Contains non-vegetarian ingredients"

        # Assign ID and save
        recipe.id = self._next_recipe_id
        self._next_recipe_id += 1

        try:
            self.recipe_store.add_recipe(recipe)
        except Exception as exc:
            logger.error("Failed to save recipe %s: %s", recipe.name, exc)
            return False, f"Save failed: {exc}"

        logger.info(f"✓ RecipeHunter added: {recipe.name} (id={recipe.id})")
        return True, recipe.name

    # ── Hunt cycle ─────────────────────────────────────────────────────────

    def hunt_once(self) -> dict:
        """
        Run one full hunter cycle.

        Returns dict with:
            targets_evaluated: int
            urls_searched: int
            recipes_extracted: int
            recipes_added: int
            duplicates_skipped: int
            failures: int
            cuisines_blacklisted: list[str]
        """
        from .cuisine_blacklister import CuisineBlacklister

        logger.info("RecipeHunter: starting hunt cycle")
        targets = self._get_targets()
        logger.info(f"RecipeHunter: {len(targets)} targets to evaluate")

        stats = {
            "targets_evaluated": 0,
            "urls_searched": 0,
            "recipes_extracted": 0,
            "recipes_added": 0,
            "duplicates_skipped": 0,
            "failures": 0,
            "cuisines_blacklisted": [],
            "recipe_names": [],
        }

        seen_urls: set[str] = set()

        for target in targets:
            stats["targets_evaluated"] += 1
            query = target["query"]
            logger.info(f"RecipeHunter: searching query={query!r} reason={target['reason']}")

            urls = self._search_urls(query, max_results=5)
            for url in urls:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                stats["urls_searched"] += 1

                success, msg = self._extract_and_save(url)
                if success:
                    stats["recipes_added"] += 1
                    stats["recipes_extracted"] += 1
                    stats["recipe_names"].append(msg)
                elif "duplicate" in msg.lower():
                    stats["duplicates_skipped"] += 1
                else:
                    stats["failures"] += 1

                # Stop if we have enough recipes this cycle
                if stats["recipes_added"] >= 5:
                    logger.info("RecipeHunter: reached max recipes per cycle (5)")
                    break

            if stats["recipes_added"] >= 5:
                break

        # Sync cuisine rejections
        try:
            blacklister = CuisineBlacklister(
                cooking_log=self.cooking_log,
                ratings=self.ratings,
                recipes=self.recipe_store,
                threshold=3,
            )
            newly_blacklisted = blacklister.sync()
            stats["cuisines_blacklisted"] = list(newly_blacklisted.keys())
        except Exception as exc:
            logger.warning("CuisineBlacklister sync failed: %s", exc)

        # Persist state
        cycles = self._cycles_completed() + 1
        self._save_state(
            last_run=datetime.now(),
            added=stats["recipes_added"],
            cycles=cycles,
            blacklisted=len(stats["cuisines_blacklisted"]),
        )

        # Notify
        try:
            self.notification_store.enqueue(
                recipes_found=stats["recipes_extracted"],
                recipes_added=stats["recipes_added"],
                cuisines_blacklisted=stats["cuisines_blacklisted"],
                recipes=stats["recipe_names"],
            )
        except Exception as exc:
            logger.warning("Failed to enqueue notification: %s", exc)

        logger.info(
            f"RecipeHunter cycle complete: added={stats['recipes_added']} "
            f"extracted={stats['recipes_extracted']} "
            f"blacklisted={stats['cuisines_blacklisted']}"
        )
        return stats

    # ── Daemon loop ─────────────────────────────────────────────────────────

    def _daemon_loop(self) -> None:
        """Main daemon loop — checks interval every 5 minutes."""
        logger.info("RecipeHunter daemon loop started")
        while self._running:
            if self._should_run():
                try:
                    stats = self.hunt_once()
                    logger.info(f"RecipeHunter cycle done: {stats}")
                except Exception as exc:
                    logger.error("RecipeHunter cycle failed: %s", exc)
            time.sleep(300)  # check every 5 minutes
        logger.info("RecipeHunter daemon loop exited")