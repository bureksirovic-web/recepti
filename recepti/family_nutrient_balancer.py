"""Family-level nutrient aggregation and RDA gap analysis."""

from datetime import date, timedelta
from typing import Optional

from recepti.models import FamilyMember, MemberNutritionSummary, Recipe


class FamilyNutrientBalancer:
    """Rolls up cooking log entries into family-level nutrient summaries."""

    NUTRIENTS = ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g",
                "iron_mg", "calcium_mg", "folate_mcg", "b12_mcg"]

    RDA_TABLE: dict[str, dict[str, float]] = {
        "toddler_1_3":   {"calories": 1050,  "protein_g": 13,   "carbs_g": 130, "fat_g": 35,
                           "fiber_g": 14,    "iron_mg": 7,      "calcium_mg": 700,  "folate_mcg": 150,  "b12_mcg": 1.0},
        "child_4_8":     {"calories": 1500,  "protein_g": 28,   "carbs_g": 190, "fat_g": 50,
                           "fiber_g": 20,    "iron_mg": 10,     "calcium_mg": 1000, "folate_mcg": 200,  "b12_mcg": 1.5},
        "child_9_13_m":  {"calories": 2100,  "protein_g": 34,   "carbs_g": 265, "fat_g": 70,
                           "fiber_g": 25,    "iron_mg": 8,      "calcium_mg": 1300, "folate_mcg": 300,  "b12_mcg": 2.0},
        "child_9_13_f":  {"calories": 1850,  "protein_g": 34,   "carbs_g": 235, "fat_g": 60,
                           "fiber_g": 23,    "iron_mg": 8,      "calcium_mg": 1300, "folate_mcg": 300,  "b12_mcg": 2.0},
        "adult_male":    {"calories": 2500,  "protein_g": 56,   "carbs_g": 320, "fat_g": 80,
                           "fiber_g": 30,    "iron_mg": 8,      "calcium_mg": 1000, "folate_mcg": 400,  "b12_mcg": 2.4},
        "adult_female":  {"calories": 1900,  "protein_g": 46,   "carbs_g": 245, "fat_g": 65,
                           "fiber_g": 25,    "iron_mg": 15,      "calcium_mg": 1000, "folate_mcg": 400,  "b12_mcg": 2.4},
        "pregnant":       {"calories": 2250,  "protein_g": 60,   "carbs_g": 285, "fat_g": 75,
                           "fiber_g": 28,    "iron_mg": 27,     "calcium_mg": 1000, "folate_mcg": 600,  "b12_mcg": 2.6},
        "lactating":     {"calories": 2600,  "protein_g": 65,   "carbs_g": 330, "fat_g": 85,
                           "fiber_g": 30,    "iron_mg": 9,      "calcium_mg": 1000, "folate_mcg": 500,  "b12_mcg": 2.8},
    }

    def __init__(self, store, recipe_store):
        self.store = store
        self.recipe_store = recipe_store

    def _rda_key(self, member: FamilyMember) -> str:
        age = member.age_years
        sex = member.sex
        if member.lactating:
            return "lactating"
        if member.pregnant:
            return "pregnant"
        if age < 1:
            return "toddler_1_3"
        if age < 4:
            return "toddler_1_3"
        if age < 10:
            return "child_4_8"
        if age < 14:
            key = "child_9_13_m" if sex == "male" else "child_9_13_f"
            return key
        if sex == "male":
            return "adult_male"
        return "adult_female"

    def rda_for_member(self, member: FamilyMember) -> dict[str, float]:
        key = self._rda_key(member)
        base = self.RDA_TABLE.get(key, self.RDA_TABLE["adult_male"])
        scale = max(0.5, min(1.5, (age := member.age_years) / 30))
        return {k: round(v * scale, 2) for k, v in base.items()}

    def _scale_nutrition(
        self, nutrition: dict[str, float], servings: float
    ) -> dict[str, float]:
        return {k: round(v * servings, 2) for k, v in nutrition.items()}

    def summarise_member(
        self,
        member: FamilyMember,
        sessions: Optional[list] = None,
        days: int = 7,
    ) -> MemberNutritionSummary:
        cutoff = date.today() - timedelta(days=days)
        if sessions is None:
            sessions = self.store.get_sessions(since=cutoff)
        target = self.rda_for_member(member)
        intake = {n: 0.0 for n in self.NUTRIENTS}
        for s in sessions:
            if member.id not in s.servings_served:
                continue
            recipe = self.recipe_store.get_recipe_by_id(s.recipe_id)
            if not recipe:
                continue
            n = recipe.nutrition_per_serving
            servings = s.servings_served[member.id]
            intake["calories"]   += round(n.calories * servings, 2)
            intake["protein_g"]  += round(n.protein_g * servings, 2)
            intake["carbs_g"]    += round(n.carbs_g * servings, 2)
            intake["fat_g"]     += round(n.fat_g * servings, 2)
            intake["fiber_g"]   += round(n.fiber_g * servings, 2)
            intake["iron_mg"]   += round(n.iron_mg * servings, 2)
            intake["calcium_mg"] += round(n.calcium_mg * servings, 2)
            intake["folate_mcg"] += round(n.folate_mcg * servings, 2)
            intake["b12_mcg"]    += round(n.b12_mcg * servings, 2)
        return MemberNutritionSummary(
            member_id=member.id,
            member_name=member.name,
            rda=target,
            intake=intake,
        )

    def family_balance(self, days: int = 7) -> list[MemberNutritionSummary]:
        summaries = []
        for member in self.store.get_members():
            summaries.append(self.summarise_member(member, days=days))
        return summaries

    def deficient_nutrients(
        self, summary: MemberNutritionSummary, threshold_pct: float = 80.0
    ) -> list[tuple[str, float, float]]:
        gaps = []
        for nutrient in self.NUTRIENTS:
            pct = summary.pct_of_rda(nutrient)
            if pct < threshold_pct:
                gaps.append((nutrient, pct, summary.gap(nutrient)))
        gaps.sort(key=lambda x: x[1])
        return gaps