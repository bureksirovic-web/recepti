"""
Search utilities for Recepti — text/semantic search over recipe collections.
Built-in keyword matching; swap in an embedding model if needed.
"""
import re
from typing import Protocol, Sequence

from recepti.models import Recipe


class Searcher(Protocol):
    """Protocol for recipe search backends."""
    def search(self, query: str, recipes: Sequence[Recipe], top_k: int = 10) -> list[tuple[Recipe, float]]:
        ...


class KeywordSearcher:
    """Simple keyword + tag search over recipes."""

    def search(self, query: str, recipes: Sequence[Recipe], top_k: int = 10) -> list[tuple[Recipe, float]]:
        """
        Score recipes by keyword match count and tag match.
        Returns list of (Recipe, score) sorted by score descending.
        """
        query_lower = query.lower()
        query_words = re.findall(r"\w+", query_lower)

        scored: list[tuple[Recipe, float]] = []
        for recipe in recipes:
            score = 0.0

            # Name match (highest weight)
            name_words = re.findall(r"\w+", recipe.name.lower())
            for qw in query_words:
                if any(qw in nw for nw in name_words):
                    score += 3.0

            # Description match
            desc_words = re.findall(r"\w+", recipe.description.lower())
            for qw in query_words:
                if any(qw in dw for dw in desc_words):
                    score += 1.5

            # Tag match
            for qw in query_words:
                if qw in recipe.tags.cuisine.lower():
                    score += 2.0
                if qw in recipe.tags.meal_type.lower():
                    score += 2.0
                for dt in recipe.tags.dietary_tags:
                    if qw in dt.lower():
                        score += 1.5

            # Ingredient name match
            for ing in recipe.ingredients:
                ing_words = re.findall(r"\w+", ing.name.lower())
                for qw in query_words:
                    if any(qw in iw for iw in ing_words):
                        score += 1.0

            if score > 0:
                scored.append((recipe, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]


# ── Text helpers ───────────────────────────────────────────────────────
def highlight_matches(text: str, query: str) -> str:
    """Wrap matching query terms in text with **bold** markers."""
    query_words = re.findall(r"\w+", query.lower())
    result = text
    for word in query_words:
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        result = pattern.sub(lambda m: f"**{m.group()}**", result)
    return result


def fuzzy_match(query: str, target: str, threshold: float = 0.7) -> bool:
    """Simple substring match — replace with proper fuzzy if needed."""
    q = query.lower().strip()
    t = target.lower().strip()
    if q in t:
        return True
    # Token overlap
    q_words = set(re.findall(r"\w+", q))
    t_words = set(re.findall(r"\w+", t))
    if not q_words or not t_words:
        return False
    overlap = len(q_words & t_words) / len(q_words)
    return overlap >= threshold