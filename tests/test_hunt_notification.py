"""Tests for HuntNotificationStore."""

import json
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from recepti.hunt_notification import HuntNotification, HuntNotificationStore


@pytest.fixture
def store_path(tmp_path):
    return str(tmp_path / "hunt_notifications.json")


@pytest.fixture
def store(store_path):
    return HuntNotificationStore(store_path)


def _load(path):
    with open(path) as f:
        return json.load(f)


class TestInit:
    def test_empty_file_on_init(self, store_path, tmp_path):
        store = HuntNotificationStore(store_path)
        assert store._notifications == []
        assert store._next_id == 1

    def test_loads_existing_data(self, store_path, tmp_path):
        store_path_obj = tmp_path / "hunt_notifications.json"
        store_path_obj.write_text(
            json.dumps([
                {
                    "id": 1,
                    "timestamp": "2025-01-01T10:00:00",
                    "recipes_found": 3,
                    "recipes_added": 2,
                    "cuisines_blacklisted": [],
                    "hunt_summary": "Hunter completed a scan",
                    "recipes": [],
                },
                {
                    "id": 2,
                    "timestamp": "2025-01-02T10:00:00",
                    "recipes_found": 5,
                    "recipes_added": 4,
                    "cuisines_blacklisted": ["punjabi"],
                    "hunt_summary": "blacklisted cuisines: punjabi",
                    "recipes": ["recipe a", "recipe b"],
                },
            ])
        )
        store = HuntNotificationStore(str(store_path_obj))
        assert len(store._notifications) == 2
        assert store._next_id == 3

    def test_handles_invalid_json(self, store_path, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json")
        store = HuntNotificationStore(str(bad_file))
        assert store._notifications == []
        assert store._next_id == 1


class TestEnqueue:
    def test_enqueue_creates_notification(self, store, store_path):
        notification = store.enqueue(
            recipes_found=3,
            recipes_added=2,
            cuisines_blacklisted=[],
            recipes=["recipe a", "recipe b"],
        )
        assert notification.id == 1
        assert notification.recipes_found == 3
        assert notification.recipes_added == 2
        assert notification.recipes == ["recipe a", "recipe b"]

    def test_enqueue_increments_id(self, store):
        n1 = store.enqueue(recipes_found=1, recipes_added=1, cuisines_blacklisted=[], recipes=[])
        n2 = store.enqueue(recipes_found=2, recipes_added=2, cuisines_blacklisted=[], recipes=[])
        assert n1.id == 1
        assert n2.id == 2
        assert n2.id != n1.id

    def test_enqueue_saves_to_disk(self, store, store_path):
        store.enqueue(recipes_found=1, recipes_added=1, cuisines_blacklisted=[], recipes=[])
        data = _load(store_path)
        assert len(data) == 1
        assert data[0]["recipes_found"] == 1

    def test_enqueue_with_cuisines_blacklisted(self, store, store_path):
        store.enqueue(
            recipes_found=2,
            recipes_added=2,
            cuisines_blacklisted=["punjabi", "croatian"],
            recipes=["r1", "r2"],
        )
        data = _load(store_path)
        assert data[0]["cuisines_blacklisted"] == ["punjabi", "croatian"]


class TestGenerateSummary:
    def test_generate_summary_recipes_only(self, store):
        s = store._generate_summary(3, [])
        assert "3 recipes" in s
        assert "Hunter added 3 recipes" in s

    def test_generate_summary_single_recipe(self, store):
        s = store._generate_summary(1, [])
        assert "1 recipe" in s

    def test_generate_summary_blacklisted_cuisines(self, store):
        s = store._generate_summary(0, ["punjabi"])
        assert "punjabi" in s
        assert "blacklisted" in s

    def test_generate_summary_single_blacklisted(self, store):
        s = store._generate_summary(0, ["croatian"])
        assert "blacklisted cuisine" in s
        assert "cuisines:" not in s

    def test_generate_summary_both(self, store):
        s = store._generate_summary(2, ["punjabi"])
        assert "2 recipe" in s
        assert "punjabi" in s

    def test_generate_summary_empty(self, store):
        s = store._generate_summary(0, [])
        assert s == "Hunter completed a scan"


class TestGetPending:
    def test_get_pending_returns_all(self, store):
        store.enqueue(recipes_found=1, recipes_added=1, cuisines_blacklisted=[], recipes=[])
        store.enqueue(recipes_found=2, recipes_added=2, cuisines_blacklisted=[], recipes=[])
        pending = store.get_pending()
        assert len(pending) == 2

    def test_get_pending_returns_copy(self, store):
        store.enqueue(recipes_found=1, recipes_added=1, cuisines_blacklisted=[], recipes=[])
        pending = store.get_pending()
        pending.clear()
        pending2 = store.get_pending()
        assert len(pending2) == 1


class TestClearPending:
    def test_clear_pending_removes_all(self, store, store_path):
        store.enqueue(recipes_found=1, recipes_added=1, cuisines_blacklisted=[], recipes=[])
        store.clear_pending()
        assert store.get_pending() == []
        data = _load(store_path)
        assert data == []


class TestGetRecent:
    def test_get_recent_respects_limit(self, store):
        for i in range(15):
            store.enqueue(recipes_found=i, recipes_added=i, cuisines_blacklisted=[], recipes=[])
        recent = store.get_recent(limit=5)
        assert len(recent) == 5

    def test_get_recent_sorted_by_timestamp_desc(self, store):
        store.enqueue(recipes_found=1, recipes_added=1, cuisines_blacklisted=[], recipes=[])
        store.enqueue(recipes_found=2, recipes_added=2, cuisines_blacklisted=[], recipes=[])
        store.enqueue(recipes_found=3, recipes_added=3, cuisines_blacklisted=[], recipes=[])
        recent = store.get_recent(limit=2)
        # Latest first (id=3 added last, so latest timestamp)
        assert recent[0].id == 3
        assert recent[1].id == 2


class TestThreadSafety:
    def test_thread_safety(self, store_path):
        store = HuntNotificationStore(store_path)
        errors = []

        def writer(thread_id):
            try:
                for i in range(10):
                    store.enqueue(
                        recipes_found=i,
                        recipes_added=i,
                        cuisines_blacklisted=[],
                        recipes=[],
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(store._notifications) == 50