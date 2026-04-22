"""Tests for meal_state.py."""

import pytest
import time
import tempfile
import os
from recepti.meal_state import MealStateStore, PendingMealSession


@pytest.fixture
def temp_store():
    tmpdir = tempfile.mkdtemp()
    store = MealStateStore(os.path.join(tmpdir, "test_pending.json"))
    yield store, tmpdir
    # cleanup


class TestPendingMealSession:
    def test_create_session(self):
        sess = PendingMealSession(
            user_id=123,
            chat_id=456,
            raw_text="ručak: šuklji",
            parsed_meals_json="[]",
            timestamp=time.time(),
            session_key="pending",
        )
        assert sess.user_id == 123
        assert sess.awaiting_disambiguation == []

    def test_session_with_disambiguation(self):
        sess = PendingMealSession(
            user_id=123,
            chat_id=456,
            raw_text="ručak",
            parsed_meals_json="[]",
            timestamp=time.time(),
            session_key="pending",
            awaiting_disambiguation=["Tea"],
        )
        assert "Tea" in sess.awaiting_disambiguation


class TestMealStateStore:
    def test_save_and_get(self, temp_store):
        store, tmpdir = temp_store
        sess = PendingMealSession(
            user_id=123,
            chat_id=456,
            raw_text="test",
            parsed_meals_json="[]",
            timestamp=time.time(),
        )
        store.save_pending(123, sess)
        retrieved = store.get_pending(123)
        assert retrieved is not None
        assert retrieved.user_id == 123

    def test_clear_pending(self, temp_store):
        store, tmpdir = temp_store
        sess = PendingMealSession(
            user_id=123,
            chat_id=456,
            raw_text="test",
            parsed_meals_json="[]",
            timestamp=time.time(),
        )
        store.save_pending(123, sess)
        store.clear_pending(123)
        assert store.get_pending(123) is None

    def test_isolation_between_users(self, temp_store):
        store, tmpdir = temp_store
        sess1 = PendingMealSession(
            user_id=1, chat_id=1, raw_text="user1", parsed_meals_json="[]",
            timestamp=time.time()
        )
        sess2 = PendingMealSession(
            user_id=2, chat_id=2, raw_text="user2", parsed_meals_json="[]",
            timestamp=time.time()
        )
        store.save_pending(1, sess1)
        store.save_pending(2, sess2)
        assert store.get_pending(1) is not None
        assert store.get_pending(2) is not None
        assert store.get_pending(1).raw_text == "user1"
        assert store.get_pending(2).raw_text == "user2"

    def test_disambiguation_flow(self, temp_store):
        store, tmpdir = temp_store
        sess = PendingMealSession(
            user_id=123,
            chat_id=456,
            raw_text="test",
            parsed_meals_json="[]",
            timestamp=time.time(),
            awaiting_disambiguation=["Tea", "Ivana"],
        )
        store.save_pending(123, sess)
        assert store.is_awaiting_disambiguation(123)
        resolved = store.resolve_disambiguation(123, "Tea")
        assert resolved
        remaining = store.get_pending(123)
        assert remaining is not None
        assert "Tea" not in remaining.awaiting_disambiguation

    def test_ttl_clears_old_pending(self, temp_store):
        store, tmpdir = temp_store
        # Manually inject old session
        old_timestamp = time.time() - (15 * 60)  # 15 minutes ago
        store._sessions[999] = {
            "user_id": 999,
            "chat_id": 999,
            "raw_text": "old",
            "parsed_meals_json": "[]",
            "timestamp": old_timestamp,
            "session_key": "pending",
            "awaiting_disambiguation": [],
        }
        store._save()
        # Should be cleared on next load
        store2 = MealStateStore(os.path.join(tmpdir, "test_pending.json"))
        assert store2.get_pending(999) is None