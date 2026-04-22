"""Tests for RecipeRatingStore."""

import json
import threading

import pytest

from recepti.rating_store import RecipeRatingStore


@pytest.fixture
def ratings_path(tmp_path):
    return str(tmp_path / "recipe_ratings.json")


@pytest.fixture
def store(ratings_path):
    return RecipeRatingStore(ratings_path)


def _load_ratings(path):
    with open(path) as f:
        return json.load(f)


class TestInit:
    def test_empty_file_on_init(self, ratings_path, tmp_path):
        store = RecipeRatingStore(ratings_path)
        assert store._ratings == []
        assert store._next_event_id == 1

    def test_loads_existing_data(self, ratings_path, tmp_path):
        ratings_path_obj = tmp_path / "recipe_ratings.json"
        ratings_path_obj.write_text(
            json.dumps(
                [
                    {
                        "event_id": 1,
                        "member_id": 1,
                        "recipe_id": 10,
                        "stars": 5,
                        "thumbs": True,
                        "date": "2025-01-01",
                    },
                    {
                        "event_id": 2,
                        "member_id": 2,
                        "recipe_id": 20,
                        "stars": 3,
                        "thumbs": None,
                        "date": "2025-01-02",
                    },
                ]
            )
        )
        store = RecipeRatingStore(str(ratings_path_obj))
        assert len(store._ratings) == 2
        assert store._next_event_id == 3

    def test_handles_invalid_json(self, ratings_path, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json")
        store = RecipeRatingStore(str(bad_file))
        assert store._ratings == []
        assert store._next_event_id == 1


class TestLogRating:
    def test_log_rating_thumbs(self, store, ratings_path):
        event = store.log_rating(member_id=1, recipe_id=31, thumbs=True)
        assert event.event_id == 1
        assert event.thumbs is True
        assert event.stars is None

        ratings = _load_ratings(ratings_path)
        assert len(ratings) == 1
        assert ratings[0]["thumbs"] is True
        assert ratings[0]["stars"] is None

    def test_log_rating_thumbs_false(self, store, ratings_path):
        event = store.log_rating(member_id=1, recipe_id=31, thumbs=False)
        assert event.thumbs is False

        ratings = _load_ratings(ratings_path)
        assert ratings[0]["thumbs"] is False

    def test_log_rating_stars(self, store, ratings_path):
        event = store.log_rating(member_id=2, recipe_id=31, stars=4)
        assert event.stars == 4
        assert event.thumbs is None

        ratings = _load_ratings(ratings_path)
        assert ratings[0]["stars"] == 4
        assert ratings[0]["thumbs"] is None

    def test_log_rating_both(self, store, ratings_path):
        event = store.log_rating(member_id=1, recipe_id=31, stars=4, thumbs=True)
        assert event.stars == 4
        assert event.thumbs is True

        ratings = _load_ratings(ratings_path)
        assert ratings[0]["stars"] == 4
        assert ratings[0]["thumbs"] is True

    def test_log_rating_validates_both_none(self, store):
        with pytest.raises(ValueError, match="At least one"):
            store.log_rating(member_id=1, recipe_id=31, stars=None, thumbs=None)

    def test_log_rating_validates_stars_range(self, store):
        with pytest.raises(ValueError, match="between 1 and 5"):
            store.log_rating(member_id=1, recipe_id=31, stars=0)
        with pytest.raises(ValueError, match="between 1 and 5"):
            store.log_rating(member_id=1, recipe_id=31, stars=6)

    def test_event_ids_increment(self, store, ratings_path):
        e1 = store.log_rating(member_id=1, recipe_id=10, thumbs=True)
        e2 = store.log_rating(member_id=2, recipe_id=20, stars=3)
        e3 = store.log_rating(member_id=1, recipe_id=30, thumbs=False)
        assert e1.event_id == 1
        assert e2.event_id == 2
        assert e3.event_id == 3

        ratings = _load_ratings(ratings_path)
        ids = [r["event_id"] for r in ratings]
        assert ids == [1, 2, 3]


class TestGetRatingsForRecipe:
    def test_get_ratings_for_recipe(self, store):
        store.log_rating(member_id=1, recipe_id=31, stars=5)
        store.log_rating(member_id=2, recipe_id=31, stars=3)
        ratings = store.get_ratings_for_recipe(31)
        assert len(ratings) == 2

    def test_get_ratings_for_recipe_nonexistent(self, store):
        ratings = store.get_ratings_for_recipe(9999)
        assert ratings == []


class TestGetRecipeAvgStars:
    def test_get_recipe_avg_stars(self, store):
        store.log_rating(member_id=1, recipe_id=10, stars=5)
        store.log_rating(member_id=2, recipe_id=10, stars=4)
        store.log_rating(member_id=1, recipe_id=10, stars=3)
        avg = store.get_recipe_avg_stars(10)
        assert avg == 4.0

    def test_get_recipe_avg_stars_no_stars(self, store):
        store.log_rating(member_id=1, recipe_id=10, thumbs=True)
        store.log_rating(member_id=2, recipe_id=10, thumbs=False)
        avg = store.get_recipe_avg_stars(10)
        assert avg is None

    def test_get_recipe_avg_stars_no_ratings(self, store):
        avg = store.get_recipe_avg_stars(9999)
        assert avg is None


class TestGetRejectedCuisines:
    def test_get_rejected_cuisines_threshold(self, store, tmp_path):
        from unittest.mock import MagicMock

        mock_rs = MagicMock()
        cuisine_map = {31: "croatian", 32: "croatian", 40: "punjabi"}

        def mock_get(id_):
            m = MagicMock()
            m.tags = MagicMock(cuisine=cuisine_map.get(id_, "unknown"))
            return m

        mock_rs.get_recipe_by_id.side_effect = mock_get

        store.log_rating(member_id=1, recipe_id=31, thumbs=False)
        store.log_rating(member_id=2, recipe_id=32, thumbs=False)
        store.log_rating(member_id=1, recipe_id=40, thumbs=False)

        rejected = store.get_rejected_cuisines(mock_rs, threshold=2)
        assert rejected.get("croatian") == 2
        assert "punjabi" not in rejected

    def test_get_rejected_cuisines_empty(self, store):
        from unittest.mock import MagicMock

        mock_rs = MagicMock()
        mock_rs.get_recipe_by_id.return_value = MagicMock(
            tags=MagicMock(cuisine="croatian")
        )

        rejected = store.get_rejected_cuisines(mock_rs, threshold=2)
        assert rejected == {}


class TestThreadSafety:
    def test_thread_safety(self, store):
        errors = []

        def writer(thread_id):
            try:
                for i in range(10):
                    store.log_rating(
                        member_id=thread_id,
                        recipe_id=10 + thread_id,
                        stars=((i % 5) + 1),
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(store._ratings) == 50