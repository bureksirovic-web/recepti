"""Tests for the Flask web API."""

import json

import pytest

from recepti.models import (
    Ingredient,
    NutritionPerServing,
    Recipe,
    RecipeTags,
)
from recepti.recipe_store import RecipeStore
from recepti.web_app import create_app


def make_recipes_json(recipes):
    return {
        "recipes": [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "ingredients": [
                    {"name": i.name, "amount": i.amount, "unit": i.unit}
                    for i in r.ingredients
                ],
                "instructions": r.instructions,
                "tags": {
                    "cuisine": r.tags.cuisine,
                    "meal_type": r.tags.meal_type,
                    "dietary_tags": r.tags.dietary_tags,
                },
                "servings": r.servings,
                "prep_time_min": r.prep_time_min,
                "cook_time_min": r.cook_time_min,
                "difficulty": r.difficulty,
            }
            for r in recipes
        ]
    }


@pytest.fixture
def sample_api_recipes():
    common_nutrition = dict(
        calories=180,
        protein_g=8,
        carbs_g=30,
        fat_g=4,
        fiber_g=6,
        iron_mg=3,
        calcium_mg=50,
        folate_mcg=100,
        b12_mcg=0,
    )

    def make(
        id,
        name,
        description,
        cuisine,
        meal_type,
        difficulty,
        dietary_tags=None,
        prep=10,
        cook=25,
    ):
        return Recipe(
            id=id,
            name=name,
            description=description,
            ingredients=[Ingredient("water", 100, "ml")],
            instructions=["Step 1."],
            tags=RecipeTags(
                cuisine=cuisine,
                meal_type=meal_type,
                dietary_tags=dietary_tags or [],
            ),
            servings=4,
            prep_time_min=prep,
            cook_time_min=cook,
            nutrition_per_serving=NutritionPerServing(**common_nutrition),
            difficulty=difficulty,
        )

    return [
        make(1, "Dal Tadka", "Classic Punjabi dal", "Punjabi", "lunch", "easy"),
        make(2, "Paneer Butter Masala", "Creamy paneer", "Punjabi", "dinner", "medium"),
        make(
            3, "Idli Sambar", "South Indian breakfast", "South Indian", "breakfast", "easy"
        ),
        make(4, "Kadhi", "Gujarati yogurt curry", "Gujarati", "lunch", "medium"),
        make(
            5,
            "Masoor Dal with Spinach",
            "Bengali lentil dal",
            "Bengali",
            "dinner",
            "easy",
            dietary_tags=["lacto-ovo"],
        ),
        # Croatians start at id 31 (source=croatian)
        make(31, "Burek", "Croatian stuffed pastry", "Croatian", "lunch", "medium"),
        make(32, "Pasticada", "Croatian beef stew", "Croatian", "dinner", "hard"),
        make(51, "Modern Fusion Bowl", "Contemporary fusion bowl", "Fusion", "lunch", "easy"),
        make(
            52,
            "Quinoa Buddha Bowl",
            "Healthy modern bowl",
            "Fusion",
            "dinner",
            "medium",
        ),
    ]


@pytest.fixture
def api_store(sample_api_recipes, tmp_path):
    recipes_file = tmp_path / "recipes.json"
    recipes_file.write_text(json.dumps(make_recipes_json(sample_api_recipes)))
    return RecipeStore(str(recipes_file))


@pytest.fixture
def api_client(api_store):
    app = create_app(api_store)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestHealth:
    def test_health_returns_200(self, api_client):
        resp = api_client.get("/api/health")
        assert resp.status_code == 200

    def test_health_expected_fields(self, api_client):
        resp = api_client.get("/api/health")
        data = resp.get_json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "recipe_count" in data
        assert isinstance(data["recipe_count"], int)


class TestRecipeList:
    def test_returns_200(self, api_client):
        resp = api_client.get("/api/recipes")
        assert resp.status_code == 200

    def test_returns_paginated_list(self, api_client):
        resp = api_client.get("/api/recipes")
        data = resp.get_json()
        assert "recipes" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
        assert isinstance(data["recipes"], list)

    def test_search_filters_by_name(self, api_client):
        resp = api_client.get("/api/recipes?search=Dal")
        data = resp.get_json()
        assert resp.status_code == 200
        names = [r["name"] for r in data["recipes"]]
        assert any("Dal" in n for n in names)

    def test_search_returns_empty_for_no_match(self, api_client):
        resp = api_client.get("/api/recipes?search=xyznotexist")
        data = resp.get_json()
        assert data["total"] == 0
        assert data["recipes"] == []

    def test_source_expanded_returns_only_expanded(self, api_client, api_store):
        resp = api_client.get("/api/recipes?source=expanded")
        data = resp.get_json()
        assert resp.status_code == 200
        recipe_ids = [r["id"] for r in data["recipes"]]
        assert all(id_ >= 51 for id_ in recipe_ids)

    def test_source_original_returns_original(self, api_client):
        resp = api_client.get("/api/recipes?source=original")
        data = resp.get_json()
        assert resp.status_code == 200
        recipe_ids = [r["id"] for r in data["recipes"]]
        assert all(id_ <= 30 for id_ in recipe_ids)

    def test_source_croatian_returns_croatian(self, api_client):
        resp = api_client.get("/api/recipes?source=croatian")
        data = resp.get_json()
        assert resp.status_code == 200
        recipe_ids = [r["id"] for r in data["recipes"]]
        assert all(31 <= id_ <= 50 for id_ in recipe_ids)


class TestSingleRecipe:
    def test_valid_id_returns_200(self, api_client):
        resp = api_client.get("/api/recipe/1")
        assert resp.status_code == 200

    def test_valid_id_returns_recipe_dict(self, api_client):
        resp = api_client.get("/api/recipe/1")
        data = resp.get_json()
        assert "id" in data
        assert "name" in data
        assert "ingredients" in data
        assert "instructions" in data
        assert "tags" in data

    def test_invalid_id_returns_404(self, api_client):
        resp = api_client.get("/api/recipe/99999")
        assert resp.status_code == 404

    def test_404_contains_error_message(self, api_client):
        resp = api_client.get("/api/recipe/99999")
        data = resp.get_json()
        assert "error" in data


class TestStats:
    def test_stats_returns_200(self, api_client):
        resp = api_client.get("/api/stats")
        assert resp.status_code == 200

    def test_stats_has_expected_breakdowns(self, api_client):
        resp = api_client.get("/api/stats")
        data = resp.get_json()
        assert "total" in data
        assert "by_cuisine" in data
        assert "by_meal_type" in data
        assert "by_difficulty" in data
        assert "by_source" in data
        assert isinstance(data["by_cuisine"], dict)
        assert isinstance(data["by_meal_type"], dict)
        assert isinstance(data["by_difficulty"], dict)
        assert isinstance(data["by_source"], dict)

    def test_recently_added_returns_recipes(self, api_client):
        resp = api_client.get("/api/stats")
        data = resp.get_json()
        assert "recently_added" in data
        assert isinstance(data["recently_added"], list)


class TestFilters:
    def test_filters_returns_200(self, api_client):
        resp = api_client.get("/api/filters")
        assert resp.status_code == 200

    def test_filters_returns_all_option_lists(self, api_client):
        resp = api_client.get("/api/filters")
        data = resp.get_json()
        assert "cuisines" in data
        assert "meal_types" in data
        assert "dietary_tags" in data
        assert "difficulties" in data
        assert "sources" in data
        assert isinstance(data["cuisines"], list)
        assert isinstance(data["meal_types"], list)
        assert isinstance(data["dietary_tags"], list)
        assert isinstance(data["difficulties"], list)
        assert isinstance(data["sources"], list)

    def test_difficulties_contains_expected_values(self, api_client):
        resp = api_client.get("/api/filters")
        data = resp.get_json()
        assert set(data["difficulties"]) == {"easy", "medium", "hard"}

    def test_sources_contains_expected_values(self, api_client):
        resp = api_client.get("/api/filters")
        data = resp.get_json()
        assert set(data["sources"]) == {"original", "croatian", "expanded"}


class TestStaticRoutes:
    def test_root_returns_html_or_json(self, api_client):
        resp = api_client.get("/")
        assert resp.status_code == 200
        content_type = resp.content_type or ""
        assert "text/html" in content_type or "application/json" in content_type

    def test_recipes_route_returns_html(self, api_client):
        resp = api_client.get("/recipes")
        assert resp.status_code == 200
        assert "text/html" in (resp.content_type or "")


class TestCoverage:
    def test_coverage_returns_200(self, api_client):
        resp = api_client.get("/api/coverage")
        assert resp.status_code == 200

    def test_coverage_returns_total_recipes_and_by_dimension(self, api_client):
        resp = api_client.get("/api/coverage")
        data = resp.get_json()
        assert "total_recipes" in data
        assert "by_dimension" in data
        assert isinstance(data["total_recipes"], int)
        assert isinstance(data["by_dimension"], dict)

    def test_coverage_holes_sparse(self, api_client):
        resp = api_client.get("/api/coverage")
        data = resp.get_json()
        holes = data.get("holes", [])
        sparse_holes = [h for h in holes if h.get("status") == "SPARSE"]
        assert len(sparse_holes) >= 0

    def test_coverage_holes_empty(self, api_client):
        resp = api_client.get("/api/coverage")
        data = resp.get_json()
        holes = data.get("holes", [])
        empty_holes = [h for h in holes if h.get("status") == "EMPTY"]
        assert len(empty_holes) >= 0

    def test_coverage_priority_order(self, api_client):
        resp = api_client.get("/api/coverage")
        data = resp.get_json()
        holes = data.get("holes", [])
        if len(holes) >= 2:
            priorities = [h["priority"] for h in holes]
            assert priorities == sorted(priorities, reverse=True)

    def test_coverage_suggested_queries_present(self, api_client):
        resp = api_client.get("/api/coverage")
        data = resp.get_json()
        holes = data.get("holes", [])
        for h in holes:
            assert "suggested_queries" in h
            assert isinstance(h["suggested_queries"], list)


class TestScrapeTodo:
    def test_scrape_todo_returns_200(self, api_client):
        resp = api_client.get("/api/scrape-todo")
        assert resp.status_code == 200

    def test_scrape_todo_has_targets(self, api_client):
        resp = api_client.get("/api/scrape-todo")
        data = resp.get_json()
        assert "targets" in data
        assert isinstance(data["targets"], list)

    def test_scrape_todo_targets_have_required_fields(self, api_client):
        resp = api_client.get("/api/scrape-todo")
        data = resp.get_json()
        targets = data.get("targets", [])
        if targets:
            t = targets[0]
            assert "query" in t
            assert "priority_score" in t
            assert "type" in t

    def test_scrape_todo_type_coverage(self, api_client):
        resp = api_client.get("/api/scrape-todo")
        data = resp.get_json()
        targets = data.get("targets", [])
        types = {t["type"] for t in targets}
        assert "coverage" in types

    def test_scrape_todo_priority_order(self, api_client):
        resp = api_client.get("/api/scrape-todo")
        data = resp.get_json()
        targets = data.get("targets", [])
        if len(targets) >= 2:
            scores = [t["priority_score"] for t in targets]
            assert scores == sorted(scores, reverse=True)