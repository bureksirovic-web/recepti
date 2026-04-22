"""Suggest complementary groceries to fill family nutrient gaps."""

from recepti.models import MemberNutritionSummary


NUTRIENT_INGREDIENTS: dict[str, list[tuple[str, float]]] = {
    "iron_mg": [
        ("leća", 6.5), ("grah", 5.5), ("šparoga", 2.1), ("blitva", 1.8),
        ("kelj", 1.6), ("pileća prsa", 0.4), ("pureća prsa", 0.4),
        ("svinjetina", 0.9), ("orasi", 2.9), ("bademi", 3.7), ("jaja", 1.8),
    ],
    "calcium_mg": [
        ("kelj", 254.0), ("mladi sir", 83.0), ("vrhnje", 65.0),
        ("grah", 147.0), ("jaja", 56.0), ("bademi", 269.0),
        ("kupus", 40.0), ("češnjak", 181.0), ("kruh", 260.0),
        ("šljiva", 6.0), ("maslinovo ulje", 1.0),
    ],
    "folate_mcg": [
        ("leća", 423.0), ("grah", 462.0), ("blitva", 14.0),
        ("kelj", 19.0), ("kupus", 43.0), ("jabuka", 5.0),
        ("pileća prsa", 4.0), ("pureća prsa", 4.0), ("svinjetina", 4.0),
    ],
    "b12_mcg": [
        ("pileća prsa", 0.1), ("pureća prsa", 0.1), ("svinjetina", 0.2),
        ("mladi sir", 0.5), ("jaja", 1.1),
    ],
    "protein_g": [
        ("leća", 25.0), ("grah", 22.3), ("pileća prsa", 22.5),
        ("pureća prsa", 19.8), ("svinjetina", 18.2),
        ("mladi sir", 11.6), ("jaja", 13.0), ("orasi", 15.2), ("bademi", 21.0),
    ],
    "fiber_g": [
        ("leća", 11.0), ("grah", 15.3), ("kelj", 4.1),
        ("bademi", 12.0), ("orasi", 6.7), ("jabuka", 2.4),
        ("kruška", 3.1), ("šljiva", 1.4),
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