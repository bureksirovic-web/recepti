"""Sync cuisine-level rejection signals to family member dislikes."""

import logging

from recepti.cooking_log import CookingLogStore
from recepti.rating_store import RecipeRatingStore
from recepti.recipe_store import RecipeStore

logger = logging.getLogger(__name__)


class CuisineBlacklister:
    """Syncs rejected cuisines from ratings to family member dislikes."""

    def __init__(
        self,
        cooking_log: CookingLogStore,
        ratings: RecipeRatingStore,
        recipes: RecipeStore,
        threshold: int = 3,
    ):
        self.cooking_log = cooking_log
        self.ratings = ratings
        self.recipes = recipes
        self.threshold = threshold

    def sync(self) -> dict[str, int]:
        """
        Sync rejected cuisines to all family member dislikes.

        Returns: {cuisine: rejection_count} for cuisines that were newly blacklisted.
        """
        rejected = self.ratings.get_rejected_cuisines(self.recipes, self.threshold)
        newly_blacklisted: dict[str, int] = {}

        for member in self.cooking_log.get_members():
            changed = False
            for cuisine, count in rejected.items():
                if cuisine not in member.dislikes:
                    member.dislikes.append(cuisine)
                    changed = True
                    newly_blacklisted[cuisine] = newly_blacklisted.get(cuisine, 0) + count

            if changed:
                self.cooking_log.add_member(member)

        return newly_blacklisted