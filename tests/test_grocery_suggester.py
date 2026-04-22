"""Tests for GrocerySuggester."""

from unittest.mock import MagicMock

import pytest

from recepti.grocery_suggester import GrocerySuggester
from recepti.models import MemberNutritionSummary


def make_summary(member_id: int, intake: dict[str, float], rda: dict[str, float]) -> MemberNutritionSummary:
    summary = MagicMock(spec=MemberNutritionSummary)
    summary.member_id = member_id
    summary.intake = intake
    summary.rda = rda
    summary.pct_of_rda = MemberNutritionSummary.pct_of_rda.__get__(summary, MemberNutritionSummary)
    summary.gap = MemberNutritionSummary.gap.__get__(summary, MemberNutritionSummary)
    return summary


class TestGrocerySuggesterInit:

    def test_init_with_empty_list(self):
        suggester = GrocerySuggester([])
        assert suggester.existing == set()

    def test_init_with_none(self):
        suggester = GrocerySuggester(None)
        assert suggester.existing == set()

    def test_init_normalizes_ingredients(self):
        suggester = GrocerySuggester(["Spinach", "  MILK  ", "eggs"])
        assert "spinach" in suggester.existing
        assert "milk" in suggester.existing
        assert "eggs" in suggester.existing


class TestSuggestForFamily:

    def test_suggest_for_family_with_empty_summaries(self):
        suggester = GrocerySuggester()
        suggestions = suggester.suggest_for_family([])
        assert suggestions == []

    def test_suggest_for_family_with_all_sufficient_nutrients(self):
        suggester = GrocerySuggester()
        summary = make_summary(1, {
            "iron_mg": 15.0, "calcium_mg": 1000.0, "folate_mcg": 400.0,
            "b12_mcg": 2.5, "protein_g": 60.0, "fiber_g": 30.0,
        }, {
            "iron_mg": 10.0, "calcium_mg": 800.0, "folate_mcg": 300.0,
            "b12_mcg": 2.0, "protein_g": 50.0, "fiber_g": 25.0,
        })
        suggestions = suggester.suggest_for_family([summary])
        assert suggestions == []

    def test_suggest_for_family_with_deficient_nutrients(self):
        suggester = GrocerySuggester()
        summary = make_summary(1, {
            "iron_mg": 3.0, "calcium_mg": 200.0, "folate_mcg": 100.0,
            "b12_mcg": 0.3, "protein_g": 10.0, "fiber_g": 5.0,
        }, {
            "iron_mg": 8.0, "calcium_mg": 800.0, "folate_mcg": 300.0,
            "b12_mcg": 2.0, "protein_g": 50.0, "fiber_g": 25.0,
        })
        suggestions = suggester.suggest_for_family([summary])
        assert len(suggestions) > 0
        assert any("leća" in s or "grah" in s or "kelj" in s or "jaja" in s for s in suggestions)

    def test_suggest_for_family_with_single_deficient_nutrient(self):
        suggester = GrocerySuggester()
        summary = make_summary(1, {
            "iron_mg": 0.0, "calcium_mg": 800.0, "folate_mcg": 300.0,
            "b12_mcg": 2.0, "protein_g": 50.0, "fiber_g": 25.0,
        }, {
            "iron_mg": 8.0, "calcium_mg": 800.0, "folate_mcg": 300.0,
            "b12_mcg": 2.0, "protein_g": 50.0, "fiber_g": 25.0,
        })
        suggestions = suggester.suggest_for_family([summary])
        assert len(suggestions) > 0

    def test_suggest_for_family_with_multiple_members(self):
        suggester = GrocerySuggester()
        summary1 = make_summary(1, {"iron_mg": 0.0, "calcium_mg": 800.0, "folate_mcg": 300.0, "b12_mcg": 2.0, "protein_g": 50.0, "fiber_g": 25.0}, {"iron_mg": 8.0, "calcium_mg": 800.0, "folate_mcg": 300.0, "b12_mcg": 2.0, "protein_g": 50.0, "fiber_g": 25.0})
        summary2 = make_summary(2, {"iron_mg": 8.0, "calcium_mg": 0.0, "folate_mcg": 300.0, "b12_mcg": 2.0, "protein_g": 50.0, "fiber_g": 25.0}, {"iron_mg": 8.0, "calcium_mg": 800.0, "folate_mcg": 300.0, "b12_mcg": 2.0, "protein_g": 50.0, "fiber_g": 25.0})
        suggestions = suggester.suggest_for_family([summary1, summary2])
        assert len(suggestions) > 0


class TestExistingIngredientsExcluded:

    def test_existing_ingredients_not_suggested(self):
        suggester = GrocerySuggester(["leća", "kelj"])
        summary = make_summary(1, {
            "iron_mg": 0.0, "calcium_mg": 0.0, "folate_mcg": 0.0,
            "b12_mcg": 0.0, "protein_g": 0.0, "fiber_g": 0.0,
        }, {
            "iron_mg": 8.0, "calcium_mg": 800.0, "folate_mcg": 300.0,
            "b12_mcg": 2.0, "protein_g": 50.0, "fiber_g": 25.0,
        })
        suggestions = suggester.suggest_for_family([summary])
        suggestion_text = " ".join(suggestions).lower()
        assert "leća" not in suggestion_text
        assert "kelj" not in suggestion_text

    def test_existing_ingredients_case_insensitive(self):
        suggester = GrocerySuggester(["LEĆA"])
        summary = make_summary(1, {
            "iron_mg": 0.0, "calcium_mg": 0.0, "folate_mcg": 0.0,
            "b12_mcg": 0.0, "protein_g": 0.0, "fiber_g": 0.0,
        }, {
            "iron_mg": 8.0, "calcium_mg": 800.0, "folate_mcg": 300.0,
            "b12_mcg": 2.0, "protein_g": 50.0, "fiber_g": 25.0,
        })
        suggestions = suggester.suggest_for_family([summary])
        suggestion_text = " ".join(suggestions).lower()
        assert "leća" not in suggestion_text


class TestSuggestForSummary:

    def test_suggest_for_summary_format(self):
        suggester = GrocerySuggester()
        summary = make_summary(1, {
            "iron_mg": 0.0, "calcium_mg": 0.0, "folate_mcg": 0.0,
            "b12_mcg": 0.0, "protein_g": 0.0, "fiber_g": 0.0,
        }, {
            "iron_mg": 8.0, "calcium_mg": 800.0, "folate_mcg": 300.0,
            "b12_mcg": 2.0, "protein_g": 50.0, "fiber_g": 25.0,
        })
        suggestions = suggester.suggest_for_summary(summary)
        if suggestions:
            assert "~" in suggestions[0]
            assert "g needed)" in suggestions[0]