"""Suggest complementary groceries to fill family nutrient gaps."""

from recepti.models import MemberNutritionSummary


NUTRIENT_INGREDIENTS: dict[str, list[tuple[str, float]]] = {
    "iron_mg": [
        ("toor dal", 5.0), ("masoor dal", 7.0), ("rajma", 7.0), ("chana dal", 7.0),
        ("spinach", 2.7), ("peanuts", 4.6), ("cashews", 6.7), ("dark chocolate 70%", 12.0),
    ],
    "calcium_mg": [
        ("milk", 125.0), ("paneer", 480.0), ("yogurt", 110.0), ("sesame seeds", 975.0),
        ("tofu", 350.0), ("fortified cereal", 250.0), ("sardines", 382.0),
    ],
    "folate_mcg": [
        ("toor dal", 423.0), ("rajma", 462.0), ("chana dal", 310.0), ("spinach", 194.0),
        ("asparagus", 149.0), ("avocado", 81.0), ("peanuts", 240.0), ("beets", 109.0),
    ],
    "b12_mcg": [
        ("paneer", 0.8), ("yogurt", 0.5), ("milk", 0.4), ("eggs", 1.1),
        ("fortified soy milk", 1.0), ("nutritional yeast", 2.4),
    ],
    "protein_g": [
        ("toor dal", 22.0), ("masoor dal", 25.0), ("rajma", 22.0), ("paneer", 18.0),
        ("peanuts", 26.0), ("cashews", 18.0), ("eggs", 13.0), ("tofu", 18.0),
    ],
    "fiber_g": [
        ("masoor dal", 31.0), ("toor dal", 15.0), ("rajma", 15.0), ("chana dal", 17.0),
        ("peanuts", 8.0), ("avocado", 7.0), ("spinach", 2.2), ("pears", 6.0),
    ],
}


class GrocerySuggester:
    """Suggest grocery additions to cover family nutrient gaps."""

    def __init__(self, existing_ingredients: list[str] | None = None):
        self.existing = {i.lower().strip() for i in (existing_ingredients or [])}

    def suggest_for_summary(
        self, summary: MemberNutritionSummary, threshold_pct: float = 80.0, top_n: int = 5
    ) -> list[str]:
        deficient = [
            (nut, pct, gap)
            for nut, pct, gap in [
                (n, summary.pct_of_rda(n), summary.gap(n))
                for n in [
                    "iron_mg", "calcium_mg", "folate_mcg", "b12_mcg",
                    "protein_g", "fiber_g",
                ]
            ]
            if pct < threshold_pct
        ]
        deficient.sort(key=lambda x: x[2], reverse=True)

        suggestions: list[tuple[str, float]] = []
        seen: set[str] = set()

        for nutrient, _, gap_mg in deficient:
            candidates = NUTRIENT_INGREDIENTS.get(nutrient, [])
            for name, per_100g in candidates:
                if name in seen or name in self.existing:
                    continue
                needed_100g = round(gap_mg / per_100g, 1) if per_100g > 0 else 0
                if 0 < needed_100g <= 300:
                    suggestions.append((name, needed_100g))
                    seen.add(name)

        suggestions.sort(key=lambda x: x[1])
        return [f"{name} (~{g:.0f}0g needed)" for name, g in suggestions[:top_n]]

    def suggest_for_family(
        self, summaries: list[MemberNutritionSummary], threshold_pct: float = 80.0
    ) -> list[str]:
        all_suggestions: list[tuple[str, int]] = []
        for summary in summaries:
            for raw in self.suggest_for_summary(summary, threshold_pct):
                name = raw.split(" (~")[0]
                all_suggestions.append((name, summary.member_id))
        unique = list(dict.fromkeys(s for s, _ in all_suggestions))
        return unique