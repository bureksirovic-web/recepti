"""Persistent recipe rating store — tracks stars and thumbs from family members."""

import json
import logging
import os
import tempfile
import threading
from datetime import date
from pathlib import Path
from recepti.models import RatingEvent

logger = logging.getLogger(__name__)


class RecipeRatingStore:

    def __init__(self, ratings_path: str):
        self.ratings_path = Path(ratings_path)
        self._ratings: list[RatingEvent] = []
        self._next_event_id: int = 1
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self.ratings_path.exists():
                self._ratings = []
                self._next_event_id = 1
                return
            try:
                with open(self.ratings_path) as f:
                    data = json.load(f)
                self._ratings = [
                    RatingEvent(
                        event_id=r["event_id"],
                        member_id=r["member_id"],
                        recipe_id=r["recipe_id"],
                        stars=r["stars"],
                        thumbs=r["thumbs"],
                        date=date.fromisoformat(r["date"]),
                    )
                    for r in data if isinstance(data, list)
                ]
                self._next_event_id = (
                    max(r.event_id for r in self._ratings) + 1 if self._ratings else 1
                )
            except Exception as e:
                logger.warning(f"Could not load recipe ratings: {e}")
                self._ratings = []
                self._next_event_id = 1

    def _atomic_save(self, data: list) -> None:
        self.ratings_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(self.ratings_path.parent), prefix=".recipe_ratings.tmp."
        )
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(data, f, indent=2, default=str)
            os.fsync(f.fileno())
        os.replace(tmp_path, self.ratings_path)

    def _save(self) -> None:
        with self._lock:
            data = [
                {
                    "event_id": r.event_id,
                    "member_id": r.member_id,
                    "recipe_id": r.recipe_id,
                    "stars": r.stars,
                    "thumbs": r.thumbs,
                    "date": r.date.isoformat(),
                }
                for r in self._ratings
            ]
            self._atomic_save(data)

    def log_rating(
        self,
        member_id: int,
        recipe_id: int,
        stars: int | None = None,
        thumbs: bool | None = None,
        log_date: date | None = None,
    ) -> RatingEvent:
        if stars is None and thumbs is None:
            raise ValueError("At least one of stars or thumbs must be non-None")
        if stars is not None and not (1 <= stars <= 5):
            raise ValueError("stars must be between 1 and 5")

        with self._lock:
            event = RatingEvent(
                event_id=self._next_event_id,
                member_id=member_id,
                recipe_id=recipe_id,
                stars=stars,
                thumbs=thumbs,
                date=log_date or date.today(),
            )
            self._ratings.append(event)
            self._next_event_id += 1
            self._save()
            return event

    def get_ratings_for_recipe(self, recipe_id: int) -> list[RatingEvent]:
        with self._lock:
            return sorted(
                [r for r in self._ratings if r.recipe_id == recipe_id],
                key=lambda r: r.date,
                reverse=True,
            )

    def get_recipe_avg_stars(self, recipe_id: int) -> float | None:
        with self._lock:
            star_ratings = [
                r.stars for r in self._ratings if r.recipe_id == recipe_id and r.stars is not None
            ]
            if not star_ratings:
                return None
            return float(sum(star_ratings) / len(star_ratings))

    def get_rejected_cuisines(self, recipe_store, threshold: int = 2) -> dict[str, int]:
        cuisine_rejections: dict[str, int] = {}
        for rating in self._ratings:
            if rating.thumbs is False:
                recipe = recipe_store.get_recipe_by_id(rating.recipe_id)
                if recipe:
                    cuisine = recipe.tags.cuisine
                    cuisine_rejections[cuisine] = cuisine_rejections.get(cuisine, 0) + 1
        return dict(
            sorted(
                [(c, n) for c, n in cuisine_rejections.items() if n >= threshold],
                key=lambda x: x[1],
                reverse=True,
            )
        )