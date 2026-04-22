"""Tests for meal_parser.py."""

import pytest
from recepti.meal_parser import (
    parse_meal_description,
    MealParsingResult,
    ParsedMeal,
    EaterEntry,
    KEYWORD_PRECHECK,
)


class TestKeywordPrecheck:
    def test_rucak_trigger(self):
        text = "danas za ručak jeli smo šuklji"
        assert any(kw in text.lower() for kw in KEYWORD_PRECHECK)

    def test_dorucak_trigger(self):
        text = "za doručak smo jeli kruh"
        assert any(kw in text.lower() for kw in KEYWORD_PRECHECK)

    def test_veceru_trigger(self):
        text = "večeru je kuhao tomi"
        assert any(kw in text.lower() for kw in KEYWORD_PRECHECK)

    def test_pojeo_trigger(self):
        text = "tomi je pojeo 2 porcije"
        assert any(kw in text.lower() for kw in KEYWORD_PRECHECK)

    def test_random_text_ignored(self):
        text = "bok kako si što radimo"
        assert not any(kw in text.lower() for kw in KEYWORD_PRECHECK)


class TestParseMealDescription:
    def test_empty_result_without_llm(self):
        # When llm_enabled=False, should return empty result
        result = parse_meal_description(
            "test text",
            ["tomi", "ivana"],
            ["šuklji"],
            llm_enabled=False,
        )
        assert isinstance(result, MealParsingResult)
        assert result.confidence == 0.0
        assert result.meals == []
        assert result.unmatched_members == []
        assert result.unmatched_recipes == []


class TestAmountParsing:
    def test_parsed_meal_amounts(self):
        # Test the ParsedMeal dataclass
        meal = ParsedMeal(
            meal_type="lunch",
            recipe_name="šuklji",
            eaters=[
                EaterEntry(member_name="tomi", amount=2.0),
                EaterEntry(member_name="ivana", amount=0.0),
            ],
        )
        assert len(meal.eaters) == 2
        assert meal.eaters[0].amount == 2.0
        assert meal.eaters[1].amount == 0.0

    def test_eater_entry_notes(self):
        eater = EaterEntry(member_name="tomi", amount=1.5, notes="brzo je jeo")
        assert eater.notes == "brzo je jeo"

    def test_parsed_meal_result(self):
        result = MealParsingResult(
            meals=[],
            confidence=0.0,
            unmatched_members=["Unknown"],
            unmatched_recipes=[],
        )
        assert result.confidence == 0.0
        assert "Unknown" in result.unmatched_members