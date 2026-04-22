"""Flask REST API for Recepti recipe browser."""

import json
import logging
import os
from datetime import datetime
from typing import Optional

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

logger = logging.getLogger(__name__)

DATA_DIR = os.getenv("RECEPTI_DATA_DIR", "data")

_CUISINE_TERMS: dict[str, list[str]] = {
    "croatian": ["hrvatski recepti", "hrvatska kuhinja"],
    "punjabi": ["punjabi recepti"],
    "mediterranean": ["mediteranski recepti"],
    "zagorje": ["zagorski recepti"],
    "dalmatian": ["dalmatinski recepti"],
    "istrian": ["istarski recepti"],
    "slavonian": ["slavonski recepti"],
}

_MEAL_TERMS: dict[str, list[str]] = {
    "breakfast": ["recepti za doručak", "brzi doručak recepti"],
    "lunch": ["recepti za ručak"],
    "dinner": ["recepti za večeru"],
    "snack": ["recepti za užinu"],
    "dessert": ["deserti", "recepti za desert"],
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


def _build_dim(all_recipes, total: int, dim: str) -> dict:
    counts: dict[str, dict] = {}
    for r in all_recipes:
        val = _get_tag_val(r, dim).lower()
        if val not in counts:
            counts[val] = {"name": val, "count": 0, "score": 0.0}
        counts[val]["count"] += 1
    for info in counts.values():
        info["score"] = round(info["count"] / total, 4)
    return counts


def _build_holes(all_recipes, total: int) -> list[dict]:
    if total == 0:
        return []
    dim_keys = ["cuisine", "meal_type", "difficulty"]

    def _counts(dim: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in all_recipes:
            val = _get_tag_val(r, dim).lower()
            counts[val] = counts.get(val, 0) + 1
        return counts

    holes: list[dict] = []
    for dim in dim_keys:
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

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")


def create_app(recipe_store) -> Flask:
    """Create and configure Flask app with RecipeStore injected."""
    app = Flask(__name__, static_folder=STATIC_DIR)
    CORS(app)

    # ── Helper ───────────────────────────────────────────────────────
    def recipe_to_dict(recipe) -> dict:
        return {
            "id": recipe.id,
            "name": recipe.name,
            "description": recipe.description,
            "ingredients": [
                {"name": i.name, "amount": i.amount, "unit": i.unit}
                for i in recipe.ingredients
            ],
            "instructions": recipe.instructions,
            "tags": {
                "cuisine": recipe.tags.cuisine,
                "meal_type": recipe.tags.meal_type,
                "dietary_tags": recipe.tags.dietary_tags,
            },
            "servings": recipe.servings,
            "prep_time_min": recipe.prep_time_min,
            "cook_time_min": recipe.cook_time_min,
            "total_time_min": recipe.prep_time_min + recipe.cook_time_min,
            "difficulty": recipe.difficulty,
            "source_url": recipe.source_url,
        }

    # ── Routes ────────────────────────────────────────────────────────

    @app.route("/api/health")
    def health():
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "recipe_count": len(recipe_store._recipes),
        })

    @app.route("/api/recipes")
    def get_recipes():
        """Paginated recipe list with filters."""
        all_recipes = recipe_store._recipes

        cuisine = request.args.get("cuisine", "").strip()
        meal_type = request.args.get("meal_type", "").strip()
        difficulty = request.args.get("difficulty", "").strip()
        search = request.args.get("search", "").strip().lower()
        source = request.args.get("source", "").strip()
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(50, max(1, int(request.args.get("per_page", 20))))

        if cuisine:
            all_recipes = [r for r in all_recipes if r.tags.cuisine == cuisine]
        if meal_type:
            all_recipes = [r for r in all_recipes if r.tags.meal_type == meal_type]
        if difficulty:
            all_recipes = [r for r in all_recipes if r.difficulty == difficulty]
        if search:
            all_recipes = [
                r for r in all_recipes
                if search in r.name.lower() or search in r.description.lower()
            ]
        if source:
            if source == "original":
                all_recipes = [r for r in all_recipes if r.id <= 30]
            elif source == "croatian":
                all_recipes = [r for r in all_recipes if 31 <= r.id <= 50]
            elif source == "expanded":
                all_recipes = [r for r in all_recipes if r.id >= 51]

        total = len(all_recipes)
        start = (page - 1) * per_page
        end = start + per_page
        page_recipes = all_recipes[start:end]

        return jsonify({
            "recipes": [recipe_to_dict(r) for r in page_recipes],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page if total > 0 else 1,
        })

    @app.route("/api/recipe/<int:recipe_id>")
    def get_recipe(recipe_id: int):
        """Single recipe by ID."""
        recipe = recipe_store.get_recipe_by_id(recipe_id)
        if not recipe:
            return jsonify({"error": "Recipe not found"}), 404
        return jsonify(recipe_to_dict(recipe))

    @app.route("/api/stats")
    def get_stats():
        """Aggregated recipe statistics."""
        all_recipes = recipe_store._recipes

        by_cuisine: dict[str, int] = {}
        by_meal_type: dict[str, int] = {}
        by_source: dict[str, int] = {"original": 0, "croatian": 0, "expanded": 0}
        by_difficulty: dict[str, int] = {"easy": 0, "medium": 0, "hard": 0}

        for r in all_recipes:
            by_cuisine[r.tags.cuisine] = by_cuisine.get(r.tags.cuisine, 0) + 1
            by_meal_type[r.tags.meal_type] = by_meal_type.get(r.tags.meal_type, 0) + 1
            by_difficulty[r.difficulty] = by_difficulty.get(r.difficulty, 0) + 1
            if r.id <= 30:
                by_source["original"] += 1
            elif r.id <= 50:
                by_source["croatian"] += 1
            else:
                by_source["expanded"] += 1

        recent = sorted(all_recipes, key=lambda r: r.id, reverse=True)[:5]

        return jsonify({
            "total": len(all_recipes),
            "by_cuisine": by_cuisine,
            "by_meal_type": by_meal_type,
            "by_source": by_source,
            "by_difficulty": by_difficulty,
            "recently_added": [recipe_to_dict(r) for r in recent],
        })

    @app.route("/api/filters")
    def get_filters():
        """Available filter options for the UI."""
        all_recipes = recipe_store._recipes

        cuisines = sorted(set(r.tags.cuisine for r in all_recipes))
        meal_types = sorted(set(r.tags.meal_type for r in all_recipes))
        dietary_tags = sorted(
            set(tag for r in all_recipes for tag in r.tags.dietary_tags)
        )
        difficulties = ["easy", "medium", "hard"]

        return jsonify({
            "cuisines": cuisines,
            "meal_types": meal_types,
            "dietary_tags": dietary_tags,
            "difficulties": difficulties,
            "sources": ["original", "croatian", "expanded"],
        })

    @app.route("/api/search")
    def search_recipes():
        """Lightweight search endpoint returning recipe suggestions.

        Query params:
            q: search query (required)
            limit: max results (default 8, max 20)
        """
        query = request.args.get("q", "").strip()
        if not query:
            return jsonify({"error": "Query parameter 'q' is required"}), 400

        limit = min(20, max(1, int(request.args.get("limit", 8))))

        query_lower = query.lower()
        scored = []

        for recipe in recipe_store._recipes:
            score = 0
            name_lower = recipe.name.lower()
            desc_lower = recipe.description.lower()

            if name_lower == query_lower:
                score = 100
            elif name_lower.startswith(query_lower):
                score = 80
            elif query_lower in name_lower:
                score = 50 + (name_lower.find(query_lower) > 0)
            elif query_lower in desc_lower:
                score = 20

            if score > 0:
                scored.append((recipe, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        results = [
            {"id": r.id, "name": r.name, "cuisine": r.tags.cuisine}
            for r, _ in scored[:limit]
        ]

        return jsonify({
            "results": results,
            "query": query,
            "total": len(results),
        })

    # ── Static file serving ─────────────────────────────────────────
    @app.route("/recipes")
    def serve_recipes():
        return send_from_directory(STATIC_DIR, "recipes.html")

    @app.route("/scrape-todo")
    def serve_scrape_todo():
        return send_from_directory(STATIC_DIR, "scrape-todo.html")

    @app.route("/nutrients")
    def serve_nutrients():
        return send_from_directory(STATIC_DIR, "nutrients.html")

    @app.route("/coverage")
    def serve_coverage():
        return send_from_directory(STATIC_DIR, "coverage.html")

    @app.route("/")
    def serve_index():
        index_path = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_path):
            return send_from_directory(STATIC_DIR, "index.html")
        return jsonify({
            "message": "Recepti API running",
            "endpoints": ["/api/recipes", "/api/recipe/<id>", "/api/stats", "/api/filters"],
        })

    @app.route("/api/nutrients")
    def get_nutrients():
        days = max(1, min(90, int(request.args.get("days", 7))))
        try:
            from recepti.cooking_log import CookingLogStore
            from recepti.family_nutrient_balancer import FamilyNutrientBalancer
            from recepti.grocery_suggester import GrocerySuggester
            store = CookingLogStore(
                os.path.join(DATA_DIR, "cooking_log.json"),
                os.path.join(DATA_DIR, "family_members.json"),
            )
            balancer = FamilyNutrientBalancer(store, recipe_store)
            suggester = GrocerySuggester(
                existing_ingredients=[
                    i.name for r in recipe_store._recipes for i in r.ingredients
                ]
            )
            summaries = balancer.family_balance(days=days)
            return jsonify({
                "days": days,
                "members": [
                    {
                        "member_id": s.member_id,
                        "member_name": s.member_name,
                        "rda": s.rda,
                        "intake": s.intake,
                        "pct_of_rda": {
                            n: s.pct_of_rda(n) for n in balancer.NUTRIENTS
                        },
                        "gaps": [
                            {"nutrient": n, "pct": s.pct_of_rda(n), "gap_mg": s.gap(n)}
                            for n in balancer.NUTRIENTS
                            if s.pct_of_rda(n) < 80
                        ],
                    }
                    for s in summaries
                ],
                "suggested_groceries": suggester.suggest_for_family(summaries),
            })
        except Exception as exc:
            logger.error("Failed to load nutrients endpoint: %s", exc)
            return jsonify({"error": "Nutrient tracking not configured yet"}), 503

    @app.route("/api/groceries")
    def get_groceries():
        try:
            from recepti.cooking_log import CookingLogStore
            from recepti.family_nutrient_balancer import FamilyNutrientBalancer
            from recepti.grocery_suggester import GrocerySuggester
            store = CookingLogStore(
                os.path.join(DATA_DIR, "cooking_log.json"),
                os.path.join(DATA_DIR, "family_members.json"),
            )
            balancer = FamilyNutrientBalancer(store, recipe_store)
            suggester = GrocerySuggester(
                existing_ingredients=[
                    i.name for r in recipe_store._recipes for i in r.ingredients
                ]
            )
            summaries = balancer.family_balance(days=7)
            suggestions = suggester.suggest_for_family(summaries)
            return jsonify({"suggestions": suggestions})
        except Exception as exc:
            logger.error("Failed to load groceries endpoint: %s", exc)
            return jsonify({"error": "Grocery suggester not configured yet"}), 503

    @app.route("/api/coverage")
    def get_coverage():
        all_recipes = recipe_store._recipes
        total = len(all_recipes)
        if total == 0:
            return jsonify({"error": "No recipes loaded"}), 503

        by_dimension = {
            "cuisine": _build_dim(all_recipes, total, "cuisine"),
            "meal_type": _build_dim(all_recipes, total, "meal_type"),
            "difficulty": _build_dim(all_recipes, total, "difficulty"),
        }

        holes = _build_holes(all_recipes, total)

        return jsonify(
            {
                "by_dimension": by_dimension,
                "holes": holes,
                "total_recipes": total,
            }
        )

    @app.route("/api/scrape-todo")
    def get_scrape_todo():
        try:
            from recepti.rating_store import RecipeRatingStore
            ratings_store = RecipeRatingStore(
                os.path.join(DATA_DIR, "recipe_ratings.json")
            )
        except Exception as exc:
            logger.warning("Ratings store unavailable: %s", exc)
            ratings_store = None

        all_recipes = recipe_store._recipes
        total = len(all_recipes)
        if total == 0:
            return jsonify({"error": "No recipes loaded"}), 503

        coverage_holes = _build_holes(all_recipes, total)

        rejected_cuisines: dict[str, int] = {}
        if ratings_store is not None:
            rejected_cuisines = ratings_store.get_rejected_cuisines(recipe_store, threshold=2)

        targets: list[dict] = []
        seen_queries: set[str] = set()

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

        if rejected_cuisines and ratings_store is not None:
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

        return jsonify(
            {
                "targets": targets[:20],
                "coverage_holes": len(coverage_holes),
                "rejected_cuisines": rejected_cuisines,
            }
        )

    return app