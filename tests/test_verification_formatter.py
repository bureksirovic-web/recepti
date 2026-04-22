"""Tests for verification_formatter.py."""

import pytest
from recepti.verification_formatter import format_verification_message
from recepti.meal_parser import MealParsingResult, ParsedMeal, EaterEntry


class TestVerificationMessage:
    def test_valid_result_format(self):
        result = MealParsingResult(
            meals=[
                ParsedMeal(
                    meal_type="lunch",
                    recipe_name="šuklji",
                    eaters=[
                        EaterEntry(member_name="tomi", amount=2.0),
                    ],
                )
            ],
            confidence=0.85,
            unmatched_members=[],
            unmatched_recipes=[],
        )
        msg = format_verification_message(result, {}, {}, "test text")
        assert "PROVJERI" in msg
        assert "RUČAK" in msg
        assert "Potvrdi" in msg
        assert "Ispravi" in msg
        assert "test text" in msg

    def test_empty_result_nisam_uspjela(self):
        result = MealParsingResult(
            meals=[],
            confidence=0.0,
            unmatched_members=[],
            unmatched_recipes=[],
        )
        msg = format_verification_message(result, {}, {}, "random")
        assert "Nisam uspjela" in msg

    def test_raw_text_reference(self):
        result = MealParsingResult(
            meals=[
                ParsedMeal(
                    meal_type="breakfast",
                    recipe_name="kruh",
                    eaters=[EaterEntry(member_name="tomi", amount=1.0)],
                )
            ],
            confidence=1.0,
            unmatched_members=[],
            unmatched_recipes=[],
        )
        long_text = "a" * 300
        msg = format_verification_message(result, {}, {}, long_text)
        assert long_text[:200] in msg
        assert "..." in msg  # truncation indicator

    def test_amount_display_nije_jela(self):
        result = MealParsingResult(
            meals=[
                ParsedMeal(
                    meal_type="lunch",
                    recipe_name="šuklji",
                    eaters=[
                        EaterEntry(member_name="tea", amount=0.0),
                    ],
                )
            ],
            confidence=0.7,
            unmatched_members=[],
            unmatched_recipes=[],
        )
        msg = format_verification_message(result, {}, {}, "")
        assert "NIJE JELA" in msg or "nije" in msg.lower()

    def test_multiple_meals(self):
        result = MealParsingResult(
            meals=[
                ParsedMeal(
                    meal_type="breakfast",
                    recipe_name="kruh",
                    eaters=[EaterEntry(member_name="tomi", amount=1.0)],
                ),
                ParsedMeal(
                    meal_type="lunch",
                    recipe_name="šuklji",
                    eaters=[EaterEntry(member_name="tomi", amount=2.0)],
                ),
            ],
            confidence=1.0,
            unmatched_members=[],
            unmatched_recipes=[],
        )
        msg = format_verification_message(result, {}, {}, "")
        assert "DORUČAK" in msg
        assert "RUČAK" in msg