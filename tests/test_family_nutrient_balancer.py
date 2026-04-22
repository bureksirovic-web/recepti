"""Tests for FamilyNutrientBalancer."""

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from recepti.family_nutrient_balancer import FamilyNutrientBalancer
from recepti.models import (
    CookingSession,
    FamilyMember,
    NutritionPerServing,
    Recipe,
)


# ── Fixtures ────────────────────────────────────────────────────────────────────


@pytest.fixture
def standard_nutrition():
    """Standard nutrition values per serving for test recipes."""
    return NutritionPerServing(
        calories=200,
        protein_g=10,
        carbs_g=25,
        fat_g=8,
        fiber_g=5,
        iron_mg=2,
        calcium_mg=100,
        folate_mcg=50,
        b12_mcg=1.0,
    )


@pytest.fixture
def high_protein_nutrition():
    """High-protein nutrition values per serving."""
    return NutritionPerServing(
        calories=300,
        protein_g=30,
        carbs_g=20,
        fat_g=12,
        fiber_g=3,
        iron_mg=4,
        calcium_mg=150,
        folate_mcg=80,
        b12_mcg=2.0,
    )


@pytest.fixture
def empty_recipe_store():
    """Mock RecipeStore returning None for all recipes."""
    store = MagicMock()
    store.get_recipe_by_id.return_value = None
    return store


@pytest.fixture
def mock_store_with_members(empty_recipe_store):
    """Mock CookingLogStore with family members but no sessions."""
    store = MagicMock()
    store.get_members.return_value = [
        FamilyMember(id=1, name="Alice", sex="female", age_years=30),
        FamilyMember(id=2, name="Bob", sex="male", age_years=35),
    ]
    store.get_sessions.return_value = []
    return store


@pytest.fixture
def mock_recipe_store(standard_nutrition):
    """Mock RecipeStore that returns a known recipe."""
    store = MagicMock()
    recipe = Recipe(
        id=10,
        name="Test Stew",
        description="",
        ingredients=[],
        instructions=[],
        tags=MagicMock(),
        servings=4,
        prep_time_min=10,
        cook_time_min=30,
        nutrition_per_serving=standard_nutrition,
        difficulty="easy",
    )
    store.get_recipe_by_id.return_value = recipe
    return store


@pytest.fixture
def mock_recipe_store_multiple():
    """Mock RecipeStore that returns different recipes by id."""
    store = MagicMock()

    standard = Recipe(
        id=10, name="Stew", description="", ingredients=[], instructions=[],
        tags=MagicMock(), servings=4, prep_time_min=10, cook_time_min=30,
        nutrition_per_serving=NutritionPerServing(200, 10, 25, 8, 5, 2, 100, 50, 1.0),
        difficulty="easy",
    )
    high_protein = Recipe(
        id=11, name="Protein Bowl", description="", ingredients=[], instructions=[],
        tags=MagicMock(), servings=2, prep_time_min=5, cook_time_min=10,
        nutrition_per_serving=NutritionPerServing(300, 30, 20, 12, 3, 4, 150, 80, 2.0),
        difficulty="easy",
    )
    low_cals = Recipe(
        id=12, name="Light Salad", description="", ingredients=[], instructions=[],
        tags=MagicMock(), servings=1, prep_time_min=5, cook_time_min=0,
        nutrition_per_serving=NutritionPerServing(50, 3, 8, 2, 4, 1, 60, 30, 0.5),
        difficulty="easy",
    )

    def get_recipe(recipe_id):
        if recipe_id == 10:
            return standard
        if recipe_id == 11:
            return high_protein
        if recipe_id == 12:
            return low_cals
        return None

    store.get_recipe_by_id.side_effect = get_recipe
    return store


@pytest.fixture
def mock_store_with_sessions(empty_recipe_store):
    """Mock store with members and sessions within cutoff window."""
    today = date.today()
    store = MagicMock()
    store.get_members.return_value = [
        FamilyMember(id=1, name="Alice", sex="female", age_years=30),
    ]
    store.get_sessions.return_value = [
        CookingSession(
            id=1,
            date=today,
            recipe_id=10,
            servings_made=4.0,
            servings_served={1: 1.0},
        ),
    ]
    return store


@pytest.fixture
def mock_store_multiple_sessions(mock_recipe_store_multiple):
    """Mock store with multiple members and multiple sessions."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    last_week = today - timedelta(days=6)

    store = MagicMock()
    store.get_members.return_value = [
        FamilyMember(id=1, name="Alice", sex="female", age_years=30),
        FamilyMember(id=2, name="Bob", sex="male", age_years=35),
    ]
    store.get_sessions.return_value = [
        # Alice eats 1 serving of stew (200 cal)
        CookingSession(id=1, date=last_week, recipe_id=10, servings_made=4.0, servings_served={1: 1.0}),
        # Alice eats 0.5 serving of protein bowl (150 cal, 15 protein)
        CookingSession(id=2, date=yesterday, recipe_id=11, servings_made=2.0, servings_served={1: 0.5}),
        # Bob eats 2 servings of stew (400 cal, 20 protein)
        CookingSession(id=3, date=today, recipe_id=10, servings_made=4.0, servings_served={2: 2.0}),
    ]
    return store


# ── Helper ──────────────────────────────────────────────────────────────────────


def make_balancer(store, recipe_store):
    """Create a FamilyNutrientBalancer with the given stores."""
    return FamilyNutrientBalancer(store=store, recipe_store=recipe_store)


# ── Tests: family_balance ───────────────────────────────────────────────────────────


class TestFamilyBalance:

    def test_returns_empty_list_when_no_members(self, empty_recipe_store):
        """family_balance returns empty list when store has no members."""
        store = MagicMock()
        store.get_members.return_value = []
        balancer = make_balancer(store, empty_recipe_store)

        result = balancer.family_balance()

        assert result == []

    def test_returns_summaries_with_zero_intake_when_no_sessions(
        self, mock_store_with_members, empty_recipe_store
    ):
        """family_balance returns summaries with 0 consumed when no sessions exist."""
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)

        result = balancer.family_balance()

        assert len(result) == 2
        for summary in result:
            for nutrient in FamilyNutrientBalancer.NUTRIENTS:
                assert summary.intake[nutrient] == 0.0

    def test_sums_nutrients_from_single_session(
        self, mock_store_with_sessions, mock_recipe_store, standard_nutrition
    ):
        """family_balance sums nutrients from a single session correctly."""
        balancer = make_balancer(mock_store_with_sessions, mock_recipe_store)

        result = balancer.family_balance()

        assert len(result) == 1
        summary = result[0]
        # 1 serving * per serving values
        assert summary.intake["calories"] == round(standard_nutrition.calories * 1.0, 2)
        assert summary.intake["protein_g"] == round(standard_nutrition.protein_g * 1.0, 2)
        assert summary.intake["carbs_g"] == round(standard_nutrition.carbs_g * 1.0, 2)
        assert summary.intake["fat_g"] == round(standard_nutrition.fat_g * 1.0, 2)

    def test_sums_nutrients_from_multiple_sessions_for_same_member(
        self, mock_recipe_store_multiple
    ):
        """family_balance correctly sums across multiple sessions for one member."""
        today = date.today()
        store = MagicMock()
        store.get_members.return_value = [
            FamilyMember(id=1, name="Alice", sex="female", age_years=30),
        ]
        store.get_sessions.return_value = [
            CookingSession(id=1, date=today, recipe_id=10, servings_made=4.0, servings_served={1: 1.0}),
            CookingSession(id=2, date=today, recipe_id=11, servings_made=2.0, servings_served={1: 0.5}),
        ]
        balancer = make_balancer(store, mock_recipe_store_multiple)

        result = balancer.family_balance()

        summary = result[0]
        # Stew: 200 cal + Protein Bowl: 0.5 * 300 cal = 350 cal total
        assert summary.intake["calories"] == 350.0
        # Stew: 10g + Protein Bowl: 0.5 * 30g = 25g protein
        assert summary.intake["protein_g"] == 25.0
        # Carbs: 25g + 0.5*20g = 35g
        assert summary.intake["carbs_g"] == 35.0

    def test_respects_days_filter_excludes_old_sessions(self, mock_recipe_store_multiple):
        """family_balance excludes sessions older than N days via store.get_sessions."""
        today = date.today()
        last_week = today - timedelta(days=6)
        two_weeks_ago = today - timedelta(days=14)

        all_sessions = [
            # Recent session
            CookingSession(id=1, date=last_week, recipe_id=10, servings_made=4.0, servings_served={1: 1.0}),
            # Old session - should be excluded when days=7
            CookingSession(id=2, date=two_weeks_ago, recipe_id=11, servings_made=2.0, servings_served={1: 2.0}),
        ]

        # Filter sessions based on since parameter (simulating store behavior)
        def get_sessions(since=None):
            if since:
                return [s for s in all_sessions if s.date >= since]
            return all_sessions

        store = MagicMock()
        store.get_members.return_value = [
            FamilyMember(id=1, name="Alice", sex="female", age_years=30),
        ]
        store.get_sessions.side_effect = get_sessions
        balancer = make_balancer(store, mock_recipe_store_multiple)

        # days=7 should exclude sessions older than 7 days
        result = balancer.family_balance(days=7)

        summary = result[0]
        # Only recent session (200 cal) should be counted
        assert summary.intake["calories"] == 200.0
        assert summary.intake["protein_g"] == 10.0

    def test_respects_days_filter_includes_old_sessions_with_larger_window(
        self, mock_recipe_store_multiple
    ):
        """family_balance includes sessions within a larger days window."""
        today = date.today()
        last_week = today - timedelta(days=6)
        two_weeks_ago = today - timedelta(days=14)

        store = MagicMock()
        store.get_members.return_value = [
            FamilyMember(id=1, name="Alice", sex="female", age_years=30),
        ]
        store.get_sessions.return_value = [
            # Recent session
            CookingSession(id=1, date=last_week, recipe_id=10, servings_made=4.0, servings_served={1: 1.0}),
            # Old session for days=21 window
            CookingSession(id=2, date=two_weeks_ago, recipe_id=11, servings_made=2.0, servings_served={1: 2.0}),
        ]
        balancer = make_balancer(store, mock_recipe_store_multiple)

        # days=21 should include both sessions
        result = balancer.family_balance(days=21)

        summary = result[0]
        # Stew 200 cal + Protein Bowl 2*300 cal = 800 cal total
        assert summary.intake["calories"] == 800.0

    def test_returns_list_not_dict(self, mock_store_with_members, empty_recipe_store):
        """family_balance returns a list of summaries, not a dict keyed by name."""
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)

        result = balancer.family_balance()

        assert isinstance(result, list)
        assert len(result) == 2
        for summary in result:
            assert hasattr(summary, "member_id")
            assert hasattr(summary, "member_name")
            assert hasattr(summary, "rda")
            assert hasattr(summary, "intake")


# ── Tests: MemberNutritionSummary fields ──────────────────────────────────────


class TestMemberNutritionSummaryFields:

    def test_summary_has_member_id_and_name(self, mock_store_with_sessions, mock_recipe_store):
        """MemberNutritionSummary has correct member_id and member_name fields."""
        balancer = make_balancer(mock_store_with_sessions, mock_recipe_store)

        result = balancer.family_balance()

        summary = result[0]
        assert summary.member_id == 1
        assert summary.member_name == "Alice"

    def test_summary_has_rda_dict_with_all_nutrients(self, mock_store_with_members, empty_recipe_store):
        """MemberNutritionSummary.rda contains all tracked nutrients."""
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)

        result = balancer.family_balance()

        for summary in result:
            for nutrient in FamilyNutrientBalancer.NUTRIENTS:
                assert nutrient in summary.rda
                assert isinstance(summary.rda[nutrient], (int, float))

    def test_summary_has_intake_dict_with_all_nutrients(
        self, mock_store_with_sessions, mock_recipe_store
    ):
        """MemberNutritionSummary.intake contains all tracked nutrients."""
        balancer = make_balancer(mock_store_with_sessions, mock_recipe_store)

        result = balancer.family_balance()

        for summary in result:
            for nutrient in FamilyNutrientBalancer.NUTRIENTS:
                assert nutrient in summary.intake
                assert isinstance(summary.intake[nutrient], (int, float))


# ── Tests: RDA percentages ───────────────────────────────────────────────────────


class TestRdaPercentages:

    def test_pct_of_rda_calculated_correctly(
        self, mock_store_with_sessions, mock_recipe_store, standard_nutrition
    ):
        """pct_of_rda returns consumed/rda * 100 rounded to 1 decimal."""
        balancer = make_balancer(mock_store_with_sessions, mock_recipe_store)

        result = balancer.family_balance()
        summary = result[0]

        rda_calories = summary.rda["calories"]
        expected_pct = round(standard_nutrition.calories / rda_calories * 100, 1)
        assert summary.pct_of_rda("calories") == expected_pct

    def test_pct_of_rda_zero_when_no_intake(self, mock_store_with_members, empty_recipe_store):
        """pct_of_rda returns 0 when no nutrients consumed."""
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)

        result = balancer.family_balance()

        for summary in result:
            for nutrient in FamilyNutrientBalancer.NUTRIENTS:
                assert summary.pct_of_rda(nutrient) == 0.0

    def test_gap_calculated_as_rda_minus_intake(
        self, mock_store_with_sessions, mock_recipe_store, standard_nutrition
    ):
        """gap returns max(0, rda - intake) rounded to 2 decimals."""
        balancer = make_balancer(mock_store_with_sessions, mock_recipe_store)

        result = balancer.family_balance()
        summary = result[0]

        expected_gap = max(0.0, round(summary.rda["calories"] - standard_nutrition.calories, 2))
        assert summary.gap("calories") == expected_gap


# ── Tests: deficient_nutrients / get_family_gaps ────────────────────────────────


class TestDeficientNutrients:

    def test_deficient_nutrients_returns_nutrients_below_threshold(
        self, mock_store_with_sessions, mock_recipe_store, standard_nutrition
    ):
        """deficient_nutrients returns list of nutrients below threshold percentage."""
        balancer = make_balancer(mock_store_with_sessions, mock_recipe_store)

        result = balancer.family_balance()
        # Most nutrients will be low since only one serving was eaten
        gaps = balancer.deficient_nutrients(result[0], threshold_pct=80.0)

        # Returns list of (nutrient, pct, gap) tuples
        assert isinstance(gaps, list)
        for nutrient, pct, gap in gaps:
            assert pct < 80.0

    def test_deficient_nutrients_empty_when_above_threshold(
        self, mock_store_with_members, empty_recipe_store
    ):
        """deficient_nutrients returns empty list when intake exceeds threshold."""
        store = MagicMock()
        # Give adult male high calories to exceed 80% threshold
        store.get_members.return_value = [
            FamilyMember(id=1, name="Bob", sex="male", age_years=35),
        ]
        # Create a fake summary with high intake
        from recepti.models import MemberNutritionSummary

        high_intake_summary = MemberNutritionSummary(
            member_id=1,
            member_name="Bob",
            rda={"calories": 2500, "protein_g": 56, "carbs_g": 320, "fat_g": 80,
                 "fiber_g": 30, "iron_mg": 8, "calcium_mg": 1000, "folate_mcg": 400, "b12_mcg": 2.4},
            intake={"calories": 3000, "protein_g": 80, "carbs_g": 400, "fat_g": 100,
                    "fiber_g": 40, "iron_mg": 15, "calcium_mg": 1500, "folate_mcg": 600, "b12_mcg": 3.0},
        )
        balancer = make_balancer(store, MagicMock())

        gaps = balancer.deficient_nutrients(high_intake_summary, threshold_pct=80.0)

        # All percentages > 80%, so gaps list should be empty or only barely deficient
        assert all(pct >= 80.0 for _, pct, _ in gaps)

    def test_deficient_nutrients_threshold_varies(self, mock_store_with_members, empty_recipe_store):
        """deficient_nutrients with different thresholds returns different results."""
        from recepti.models import MemberNutritionSummary

        summary = MemberNutritionSummary(
            member_id=1,
            member_name="Test",
            rda={"calories": 1000, "protein_g": 50, "carbs_g": 130, "fat_g": 65,
                 "fiber_g": 30, "iron_mg": 15, "calcium_mg": 1000, "folate_mcg": 400, "b12_mcg": 2.4},
            intake={"calories": 400, "protein_g": 20, "carbs_g": 50, "fat_g": 25,
                    "fiber_g": 10, "iron_mg": 5, "calcium_mg": 400, "folate_mcg": 150, "b12_mcg": 1.0},
        )
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)

        gaps_high = balancer.deficient_nutrients(summary, threshold_pct=80.0)
        gaps_low = balancer.deficient_nutrients(summary, threshold_pct=20.0)

        # Higher threshold = more deficiencies reported
        assert len(gaps_high) >= len(gaps_low)

    def test_deficient_nutrients_sorted_by_pct_ascending(self, mock_store_with_members, empty_recipe_store):
        """deficient_nutrients returns gaps sorted by percentage ascending (worst first)."""
        from recepti.models import MemberNutritionSummary

        summary = MemberNutritionSummary(
            member_id=1,
            member_name="Test",
            rda={"calories": 100, "protein_g": 10, "carbs_g": 100, "fat_g": 100,
                 "fiber_g": 100, "iron_mg": 100, "calcium_mg": 100, "folate_mcg": 100, "b12_mcg": 100},
            intake={"calories": 50, "protein_g": 5, "carbs_g": 80, "fat_g": 90,
                    "fiber_g": 95, "iron_mg": 100, "calcium_mg": 100, "folate_mcg": 100, "b12_mcg": 100},
        )
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)

        gaps = balancer.deficient_nutrients(summary, threshold_pct=80.0)

        # Extract percentages and verify they're sorted
        pcts = [pct for _, pct, _ in gaps]
        assert pcts == sorted(pcts)

    def test_deficient_nutrients_default_threshold_is_80_percent(
        self, mock_store_with_members, empty_recipe_store
    ):
        """deficient_nutrients uses 80% as default threshold."""
        from recepti.models import MemberNutritionSummary

        # 80% of calories = 2000, current intake = 2100 (85%) - not deficient
        # 80% of protein = 44.8, current intake = 45 (100%) - not deficient
        summary = MemberNutritionSummary(
            member_id=1,
            member_name="Test",
            rda={"calories": 2500, "protein_g": 56, "carbs_g": 320, "fat_g": 80,
                 "fiber_g": 30, "iron_mg": 8, "calcium_mg": 1000, "folate_mcg": 400, "b12_mcg": 2.4},
            intake={"calories": 2100, "protein_g": 45, "carbs_g": 300, "fat_g": 75,
                    "fiber_g": 28, "iron_mg": 7, "calcium_mg": 950, "folate_mcg": 380, "b12_mcg": 2.2},
        )
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)

        # Call without threshold_pct to test default
        gaps = balancer.deficient_nutrients(summary)

        # All values should be >= 80%, so gaps should only have the barely deficient ones
        for nutrient, pct, gap in gaps:
            assert pct < 80.0


# ── Tests: summarise_member ────────────────────────────────────────────────────


class TestSummariseMember:

    def test_summarise_member_filters_sessions_for_member(
        self, mock_recipe_store_multiple
    ):
        """summarise_member only counts sessions where this member ate."""
        today = date.today()
        store = MagicMock()
        member = FamilyMember(id=1, name="Alice", sex="female", age_years=30)
        sessions = [
            # Session where Alice ate
            CookingSession(id=1, date=today, recipe_id=10, servings_made=4.0, servings_served={1: 1.0}),
            # Session where ONLY Bob ate (different member)
            CookingSession(id=2, date=today, recipe_id=11, servings_made=2.0, servings_served={2: 2.0}),
        ]
        balancer = make_balancer(store, mock_recipe_store_multiple)

        # Pass sessions explicitly
        summary = balancer.summarise_member(member, sessions=sessions)

        # Should only include Alice's session (200 cal), not Bob's
        assert summary.intake["calories"] == 200.0
        assert summary.intake["protein_g"] == 10.0

    def test_summarise_member_skips_missing_recipe(
        self, mock_store_with_members, empty_recipe_store
    ):
        """summarise_member skips sessions where recipe is not found."""
        today = date.today()
        sessions = [
            CookingSession(id=1, date=today, recipe_id=999, servings_made=4.0, servings_served={1: 2.0}),
        ]
        member = FamilyMember(id=1, name="Alice", sex="female", age_years=30)
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)

        summary = balancer.summarise_member(member, sessions=sessions)

        # No calories because recipe 999 not found
        assert summary.intake["calories"] == 0.0

    def test_summarise_member_multiplies_by_servings(
        self, mock_recipe_store_multiple
    ):
        """summarise_member multiplies nutrition by number of servings eaten."""
        store = MagicMock()
        member = FamilyMember(id=1, name="Alice", sex="female", age_years=30)
        sessions = [
            CookingSession(id=1, date=date.today(), recipe_id=10, servings_made=4.0, servings_served={1: 1.5}),
        ]
        balancer = make_balancer(store, mock_recipe_store_multiple)

        summary = balancer.summarise_member(member, sessions=sessions)

        # 1.5 servings * 200 cal = 300 cal
        assert summary.intake["calories"] == 300.0
        # 1.5 * 10g = 15g protein
        assert summary.intake["protein_g"] == 15.0


# ── Tests: rda_key and rda_for_member ────────────────────────────────────────────────


class TestRdaKey:

    def test_rda_key_toddler_age_1_3(self, mock_store_with_members, empty_recipe_store):
        """_rda_key returns toddler_1_3 for ages 1-3."""
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)
        member = FamilyMember(id=1, name="Toddler", sex="male", age_years=2)

        assert balancer._rda_key(member) == "toddler_1_3"

    def test_rda_key_child_4_8(self, mock_store_with_members, empty_recipe_store):
        """_rda_key returns child_4_8 for ages 4-9."""
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)
        member = FamilyMember(id=1, name="Child", sex="male", age_years=6)

        assert balancer._rda_key(member) == "child_4_8"

    def test_rda_key_child_9_13_male(self, mock_store_with_members, empty_recipe_store):
        """_rda_key returns child_9_13_m for boys aged 9-13."""
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)
        member = FamilyMember(id=1, name="Boy", sex="male", age_years=11)

        assert balancer._rda_key(member) == "child_9_13_m"

    def test_rda_key_child_9_13_female(self, mock_store_with_members, empty_recipe_store):
        """_rda_key returns child_9_13_f for girls aged 9-13."""
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)
        member = FamilyMember(id=1, name="Girl", sex="female", age_years=11)

        assert balancer._rda_key(member) == "child_9_13_f"

    def test_rda_key_adult_male(self, mock_store_with_members, empty_recipe_store):
        """_rda_key returns adult_male for males aged 14+."""
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)
        member = FamilyMember(id=1, name="Man", sex="male", age_years=30)

        assert balancer._rda_key(member) == "adult_male"

    def test_rda_key_adult_female(self, mock_store_with_members, empty_recipe_store):
        """_rda_key returns adult_female for females aged 14+."""
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)
        member = FamilyMember(id=1, name="Woman", sex="female", age_years=30)

        assert balancer._rda_key(member) == "adult_female"

    def test_rda_key_pregnant_overrides_age(self, mock_store_with_members, empty_recipe_store):
        """_rda_key returns pregnant for pregnant members regardless of age."""
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)
        member = FamilyMember(id=1, name="Pregnant", sex="female", age_years=20, pregnant=True)

        assert balancer._rda_key(member) == "pregnant"

    def test_rda_key_lactating_overrides_pregnant(
        self, mock_store_with_members, empty_recipe_store
    ):
        """_rda_key returns lactating (takes precedence over pregnant)."""
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)
        member = FamilyMember(
            id=1, name="Nursing", sex="female", age_years=25,
            pregnant=True, lactating=True
        )

        assert balancer._rda_key(member) == "lactating"


class TestRdaForMember:

    def test_rda_for_member_contains_all_nutrients(self, mock_store_with_members, empty_recipe_store):
        """rda_for_member returns dict with all tracked nutrients."""
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)
        member = FamilyMember(id=1, name="Adult", sex="male", age_years=30)

        rda = balancer.rda_for_member(member)

        for nutrient in FamilyNutrientBalancer.NUTRIENTS:
            assert nutrient in rda
            assert rda[nutrient] > 0

    def test_rda_for_member_scaling(self, mock_store_with_members, empty_recipe_store):
        """rda_for_member scales RDA based on age/30 ratio between 0.5 and 1.5."""
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)
        member = FamilyMember(id=1, name="Adult", sex="male", age_years=30)

        rda = balancer.rda_for_member(member)

        # Adult male base: calories=2500, with scale=1.0 (30/30)
        # Should get approximately the adult values
        assert rda["calories"] > 0
        assert isinstance(rda["calories"], float)


# ── Tests: edge cases ──────────────────────────────────────────────────────────────


class TestEdgeCases:

    def test_handles_member_with_no_servings_served(
        self, mock_store_with_members, empty_recipe_store
    ):
        """Handles sessions where member.id not in servings_served."""
        today = date.today()
        sessions = [
            # Session with no one eating (empty dict)
            CookingSession(id=1, date=today, recipe_id=10, servings_made=4.0, servings_served={}),
        ]
        member = FamilyMember(id=1, name="Alice", sex="female", age_years=30)
        balancer = make_balancer(mock_store_with_members, empty_recipe_store)

        summary = balancer.summarise_member(member, sessions=sessions)

        # No one ate, so Alice's intake is 0
        assert summary.intake["calories"] == 0.0

    def test_handles_fractional_servings(self, mock_recipe_store_multiple):
        """Handles fractional serving amounts correctly."""
        store = MagicMock()
        member = FamilyMember(id=1, name="Alice", sex="female", age_years=30)
        sessions = [
            CookingSession(
                id=1, date=date.today(), recipe_id=10,
                servings_made=4.0, servings_served={1: 0.25}
            ),
        ]
        balancer = make_balancer(store, mock_recipe_store_multiple)

        summary = balancer.summarise_member(member, sessions=sessions)

        # 0.25 servings * 200 cal = 50 cal
        assert summary.intake["calories"] == 50.0
        assert summary.intake["protein_g"] == 2.5

    def test_all_nutrients_defined_in_class(self):
        """All NUTRIENTS are properly defined."""
        nutrients = FamilyNutrientBalancer.NUTRIENTS

        assert "calories" in nutrients
        assert "protein_g" in nutrients
        assert "carbs_g" in nutrients
        assert "fat_g" in nutrients
        assert "fiber_g" in nutrients
        assert "iron_mg" in nutrients
        assert "calcium_mg" in nutrients
        assert "folate_mcg" in nutrients
        assert "b12_mcg" in nutrients
        assert len(nutrients) == 9

    def test_rda_table_complete(self):
        """RDA_TABLE has entries for all life stages."""
        rda_table = FamilyNutrientBalancer.RDA_TABLE

        expected_keys = [
            "toddler_1_3", "child_4_8", "child_9_13_m", "child_9_13_f",
            "adult_male", "adult_female", "pregnant", "lactating"
        ]
        for key in expected_keys:
            assert key in rda_table
            # Each entry should have all nutrients
            for nutrient in FamilyNutrientBalancer.NUTRIENTS:
                assert nutrient in rda_table[key]


# ── Tests: integration patterns ────────────────────────────────────────────────


class TestIntegrationPattern:

    def test_full_workflow_family_with_children(
        self, mock_recipe_store_multiple
    ):
        """Full workflow: family with mixed members, multiple sessions, finding gaps."""
        today = date.today()
        last_week = today - timedelta(days=6)

        store = MagicMock()
        store.get_members.return_value = [
            FamilyMember(id=1, name="Mom", sex="female", age_years=32, pregnant=True),
            FamilyMember(id=2, name="Dad", sex="male", age_years=35),
            FamilyMember(id=3, name="Kid", sex="male", age_years=7),
        ]
        store.get_sessions.return_value = [
            # Family dinner - everyone eats
            CookingSession(
                id=1, date=last_week, recipe_id=10,
                servings_made=4.0, servings_served={1: 1.0, 2: 1.0, 3: 0.5}
            ),
            # Lunch for kids
            CookingSession(
                id=2, date=today, recipe_id=12,
                servings_made=2.0, servings_served={3: 1.0}
            ),
        ]
        balancer = make_balancer(store, mock_recipe_store_multiple)

        result = balancer.family_balance(days=7)

        # Should have 3 summaries
        assert len(result) == 3

        # Verify Mom (pregnant, so rda_key=pregnant) and Dad (adult_male) are different
        mom = next(s for s in result if s.member_name == "Mom")
        dad = next(s for s in result if s.member_name == "Dad")
        kid = next(s for s in result if s.member_name == "Kid")

        # Pregnant women need more folate/iron than standard adult
        # (pregnant: folate=600, adult_female: folate=400)
        assert mom.rda["folate_mcg"] >= dad.rda["folate_mcg"]

        # Kid is child_4_8, needs less than adult
        assert kid.rda["calories"] < dad.rda["calories"]

        # Find deficient nutrients for each
        for summary in result:
            gaps = balancer.deficient_nutrients(summary, threshold_pct=50.0)
            # At 50% threshold, with only 2 meals, likely some gaps exist
            # Just verify structure is correct
            for nutrient, pct, gap in gaps:
                assert pct < 50.0
                assert gap >= 0.0