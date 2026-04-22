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

    # ── Static file serving ─────────────────────────────────────────
    @app.route("/recipes")
    def serve_recipes():
        return send_from_directory(STATIC_DIR, "recipes.html")

    @app.route("/nutrients")
    def serve_nutrients():
        return send_from_directory(STATIC_DIR, "nutrients.html")

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

    return app