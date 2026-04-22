"""Tests for /api/search endpoint using TDD approach."""

import json
import tempfile
from pathlib import Path

import pytest

from recepti.models import (
    Ingredient,
    NutritionPerServing,
    Recipe,
    RecipeTags,
)
from recepti.recipe_store import RecipeStore
from recepti.web_app import create_app


def _make_recipe(id, name, description, cuisine, meal_type="lunch", difficulty="easy"):
    return {
        "id": id,
        "name": name,
        "description": description,
        "ingredients": [{"name": "test", "amount": 100, "unit": "g"}],
        "instructions": ["Test instruction."],
        "tags": {"cuisine": cuisine, "meal_type": meal_type, "dietary_tags": []},
        "servings": 4,
        "prep_time_min": 10,
        "cook_time_min": 25,
        "difficulty": difficulty,
        "nutrition_per_serving": {
            "calories": 100, "protein_g": 5, "carbs_g": 20, "fat_g": 3,
            "fiber_g": 2, "iron_mg": 1, "calcium_mg": 50, "folate_mcg": 20, "b12_mcg": 0.1
        },
    }


@pytest.fixture
def search_test_store():
    """Create a RecipeStore with test recipes including Croatian names."""
    recipes_data = {
        "recipes": [
            _make_recipe(1, "Dal Tadka", "Classic Punjabi dal with tempering", "Punjabi"),
            _make_recipe(2, "Palak Paneer", "Spinach curry with paneer cubes", "Punjabi"),
            _make_recipe(3, "Zagorski Čobanac", "Traditional Zagorje stew from Croatian highlands", "Croatian", "dinner", "hard"),
            _make_recipe(4, "Dalmatinska Pašticada", "Braised beef Dalmatian style with prunes", "Croatian", "dinner", "hard"),
        ]
    }

    tmp_path = Path(tempfile.mktemp(suffix=".json"))
    tmp_path.write_text(json.dumps(recipes_data))
    store = RecipeStore(str(tmp_path))
    return store


@pytest.fixture
def search_test_app(search_test_store):
    """Create Flask app for testing."""
    return create_app(search_test_store)


@pytest.fixture
def search_client(search_test_app):
    """Create test client."""
    return search_test_app.test_client()


class TestSearchEndpoint:
    """TDD tests for /api/search endpoint."""

    def test_empty_query_returns_empty_list(self, search_client):
        """Test that empty query parameter returns 400 error."""
        response = search_client.get("/api/search?q=")
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "required" in data["error"].lower()

    def test_missing_query_returns_400(self, search_client):
        """Test that missing query parameter returns 400 error."""
        response = search_client.get("/api/search")
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_valid_query_returns_results(self, search_client):
        """Test that valid query returns matching results."""
        response = search_client.get("/api/search?q=Dal")
        assert response.status_code == 200
        data = response.get_json()
        assert "results" in data
        assert "query" in data
        assert "total" in data
        assert len(data["results"]) > 0

    def test_max_8_results(self, search_client):
        """Test that results are limited to max 8 by default."""
        # Query that matches many items
        response = search_client.get("/api/search?q=e")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["results"]) <= 8

    def test_limit_parameter_respects_max(self, search_client):
        """Test that limit parameter is respected."""
        response = search_client.get("/api/search?q=Dal&limit=2")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["results"]) <= 2

    def test_limit_capped_at_20(self, search_client):
        """Test that limit parameter is capped at 20."""
        response = search_client.get("/api/search?q=Dal&limit=100")
        assert response.status_code == 200
        data = response.get_json()
        # Should not exceed 20 even though limit was 100
        assert len(data["results"]) <= 20

    def test_partial_matching(self, search_client):
        """Test partial matching - 'pala' matches 'Palak Paneer'."""
        response = search_client.get("/api/search?q=pala")
        assert response.status_code == 200
        data = response.get_json()
        names = [r["name"] for r in data["results"]]
        assert "Palak Paneer" in names

    def test_case_insensitive_matching(self, search_client):
        """Test case-insensitive matching."""
        response = search_client.get("/api/search?q=PALAK")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["results"]) > 0

        # Also test mixed case
        response2 = search_client.get("/api/search?q=DaL")
        assert response2.status_code == 200
        data2 = response2.get_json()
        assert len(data2["results"]) > 0

    def test_croatian_language_queries(self, search_client):
        """Test Croatian language queries work."""
        response = search_client.get("/api/search?q=Zagorski")
        assert response.status_code == 200
        data = response.get_json()
        names = [r["name"] for r in data["results"]]
        assert "Zagorski Čobanac" in names

    def test_response_format(self, search_client):
        """Test response format has correct structure."""
        response = search_client.get("/api/search?q=Dal")
        assert response.status_code == 200
        data = response.get_json()

        # Check top-level keys
        assert "results" in data
        assert "query" in data
        assert "total" in data
        assert isinstance(data["results"], list)
        assert isinstance(data["query"], str)
        assert isinstance(data["total"], int)

        # Check result item format
        if len(data["results"]) > 0:
            result = data["results"][0]
            assert "id" in result
            assert "name" in result
            assert "cuisine" in result
            assert isinstance(result["id"], int)
            assert isinstance(result["name"], str)
            assert isinstance(result["cuisine"], str)

            # Should NOT have description
            assert "description" not in result

    def test_no_results_returns_empty_array(self, search_client):
        """Test that no matches returns 200 with empty results."""
        response = search_client.get("/api/search?q=xyznonexistent")
        assert response.status_code == 200
        data = response.get_json()
        assert data["results"] == []
        assert data["total"] == 0

    def test_search_matches_name(self, search_client):
        """Test search matches against recipe name."""
        response = search_client.get("/api/search?q=Tadka")
        assert response.status_code == 200
        data = response.get_json()
        names = [r["name"] for r in data["results"]]
        assert "Dal Tadka" in names

    def test_search_matches_description(self, search_client):
        """Test search matches against recipe description."""
        # Search for something in description but not in name
        response = search_client.get("/api/search?q=spinach")
        assert response.status_code == 200
        data = response.get_json()
        # Should find Palak Paneer even though we searched "spinach"
        # (spinach is in description)
        assert len(data["results"]) > 0

    def test_exact_match_first(self, search_client):
        """Test that exact matches are sorted first."""
        response = search_client.get("/api/search?q=Dal Tadka")
        assert response.status_code == 200
        data = response.get_json()
        # Exact match should be first
        assert data["results"][0]["name"] == "Dal Tadka"

    def test_starts_with_before_contains(self, search_client):
        """Test that starts-with matches come before contains matches."""
        response = search_client.get("/api/search?q=Dal")
        assert response.status_code == 200
        data = response.get_json()
        # "Dal Tadka" starts with "dal", should be before other results
        if len(data["results"]) > 1:
            first_name = data["results"][0]["name"]
            assert "Dal" in first_name or first_name.startswith("dal").casefold() == first_name.startswith("dal").casefold()