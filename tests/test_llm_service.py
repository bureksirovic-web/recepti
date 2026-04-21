"""Tests for llm_service."""

import os
from unittest.mock import MagicMock, patch

import pytest
import recepti.llm_service as llm_mod

from recepti.llm_service import (
    call_openrouter,
    scale_ingredients_for_family,
    suggest_recipe,
)


class TestCallOpenrouter:
    def test_raises_runtime_error_when_api_key_empty(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=True):
            with patch.object(llm_mod, "OPENROUTER_API_KEY", ""):
                with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
                    call_openrouter("test prompt")

    def test_returns_content_on_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": "  test  "}}]}
        with patch.object(llm_mod, "OPENROUTER_API_KEY", "test-key"):
            with patch("recepti.llm_service.requests.post", return_value=mock_response) as m:
                result = call_openrouter("test")
                assert result == "test"
                m.assert_called_once()


class TestSuggestRecipe:
    def test_returns_error_dict_on_failure(self):
        with patch.object(llm_mod, "OPENROUTER_API_KEY", "test-key"):
            with patch("recepti.llm_service.requests.post", side_effect=Exception("err")):
                r = suggest_recipe(["x"], family_size=4)
                assert r["recipe_id"] == "error"

    def test_returns_error_dict_on_bad_status(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "err"
        with patch.object(llm_mod, "OPENROUTER_API_KEY", "test-key"):
            with patch("recepti.llm_service.requests.post", return_value=mock_response):
                r = suggest_recipe(["x"], family_size=4)
                assert r["recipe_id"] == "error"


class TestScaleIngredientsForFamily:
    def test_scales_4_to_9_servings(self):
        ings = [{"name": "r", "amount": "200", "unit": "g"}, {"name": "d", "amount": "100", "unit": "g"}]
        r = scale_ingredients_for_family(ings, 4, 9)
        assert r[0]["amount"] == "450.0"
        assert r[1]["amount"] == "225.0"

    def test_zero_target_returns_original(self):
        ings = [{"name": "r", "amount": "200", "unit": "g"}]
        r = scale_ingredients_for_family(ings, 4, 0)
        assert r == ings

    def test_negative_target_returns_original(self):
        ings = [{"name": "r", "amount": "200", "unit": "g"}]
        r = scale_ingredients_for_family(ings, 4, -2)
        assert r == ings

    def test_zero_original_returns_original(self):
        ings = [{"name": "r", "amount": "200", "unit": "g"}]
        r = scale_ingredients_for_family(ings, 0, 4)
        assert r == ings

    def test_parses_decimal_amounts(self):
        ings = [{"name": "o", "amount": "2.5", "unit": "tbsp"}]
        r = scale_ingredients_for_family(ings, 2, 4)
        assert r[0]["amount"] == "5.0"


class TestModuleImports:
    def test_imports_with_api_key(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            import importlib
            import recepti.llm_service
            importlib.reload(recepti.llm_service)
            assert recepti.llm_service.OPENROUTER_API_KEY == "test-key"


class TestPromptSanitization:
    def test_strips_json_fence(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '```json\n{"recipe_name":"T","recipe_id":"new","why_this_recipe":"","scaling_notes":"","ingredients":[]}\n```'
                    }
                }
            ]
        }
        with patch.object(llm_mod, "OPENROUTER_API_KEY", "test-key"):
            with patch("recepti.llm_service.requests.post", return_value=mock_response):
                r = suggest_recipe(["x"], family_size=2)
                assert r["recipe_name"] == "T"

    def test_strips_plain_fence(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '```\n{"recipe_name":"P","recipe_id":"new","why_this_recipe":"","scaling_notes":"","ingredients":[]}\n```'
                    }
                }
            ]
        }
        with patch.object(llm_mod, "OPENROUTER_API_KEY", "test-key"):
            with patch("recepti.llm_service.requests.post", return_value=mock_response):
                r = suggest_recipe(["x"], family_size=2)
                assert r["recipe_name"] == "P"