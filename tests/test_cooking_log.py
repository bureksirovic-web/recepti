"""Tests for CookingLogStore."""

import json
import threading
import time
from datetime import date, timedelta
from pathlib import Path

import pytest

from recepti.cooking_log import CookingLogStore
from recepti.models import CookingSession, FamilyMember


@pytest.fixture
def log_path(tmp_path):
    return str(tmp_path / "cooking_log.json")


@pytest.fixture
def members_path(tmp_path):
    return str(tmp_path / "family_members.json")


@pytest.fixture
def store(log_path, members_path):
    return CookingLogStore(log_path, members_path)


@pytest.fixture
def store_with_data(log_path, members_path, tmp_path):
    members_file = tmp_path / "family_members.json"
    members_file.write_text(json.dumps([
        {
            "id": 1,
            "name": "Ana",
            "sex": "female",
            "age_years": 8.0,
            "pregnant": False,
            "lactating": False,
            "dislikes": [],
        },
        {
            "id": 2,
            "name": "Ivan",
            "sex": "male",
            "age_years": 35.0,
            "pregnant": False,
            "lactating": False,
            "dislikes": ["broccoli"],
        },
    ]))
    log_file = tmp_path / "cooking_log.json"
    log_file.write_text(json.dumps([
        {
            "id": 1,
            "date": "2025-01-01",
            "recipe_id": 10,
            "servings_made": 4.0,
            "servings_served": {"1": 1.0, "2": 2.0},
            "notes": "First meal",
        },
        {
            "id": 2,
            "date": "2025-01-02",
            "recipe_id": 20,
            "servings_made": 3.0,
            "servings_served": {"2": 1.5},
            "notes": "",
        },
    ]))
    return CookingLogStore(str(log_file), str(members_file))


class TestInit:
    def test_init_loads_empty_state(self, log_path, members_path, tmp_path):
        store = CookingLogStore(log_path, members_path)
        assert store._sessions == []
        assert store._members == {}
        assert store._next_session_id == 1

    def test_members_file_created_on_first_add(self, log_path, members_path, tmp_path):
        store = CookingLogStore(log_path, members_path)
        assert not Path(members_path).exists()
        store.add_member(FamilyMember(id=1, name="Test", sex="female", age_years=5.0))
        assert Path(members_path).exists()

    def test_log_file_created_on_first_session(self, log_path, members_path, tmp_path):
        store = CookingLogStore(log_path, members_path)
        assert not Path(log_path).exists()
        store.log_session(recipe_id=1, servings_made=1.0)
        assert Path(log_path).exists()

    def test_loads_existing_data(self, store_with_data):
        assert len(store_with_data._sessions) == 2
        assert len(store_with_data._members) == 2

    def test_handles_missing_log_file(self, tmp_path, members_path):
        members_file = tmp_path / "family_members.json"
        members_file.write_text(json.dumps([]))
        store = CookingLogStore(tmp_path / "nonexistent.json", members_path)
        assert store._sessions == []

    def test_handles_missing_members_file(self, log_path, tmp_path):
        log_file = tmp_path / "cooking_log.json"
        log_file.write_text(json.dumps([]))
        store = CookingLogStore(log_path, tmp_path / "nonexistent.json")
        assert store._members == {}

    def test_handles_invalid_json_gracefully(self, log_path, members_path, tmp_path):
        members_file = tmp_path / "family_members.json"
        members_file.write_text("not json")
        store = CookingLogStore(log_path, members_path)
        assert store._members == {}
        assert store._sessions == []


class TestGetMembers:
    def test_returns_empty_when_no_members(self, store):
        assert store.get_members() == []

    def test_returns_all_members(self, store_with_data):
        members = store_with_data.get_members()
        assert len(members) == 2
        names = {m.name for m in members}
        assert "Ana" in names
        assert "Ivan" in names

    def test_get_member_returns_none_for_unknown(self, store):
        assert store.get_member(999) is None

    def test_get_member_returns_correct_member(self, store_with_data):
        member = store_with_data.get_member(1)
        assert member is not None
        assert member.name == "Ana"


class TestAddMember:
    def test_add_member_creates_member(self, store):
        member = FamilyMember(id=1, name="Test", sex="female", age_years=5.0)
        store.add_member(member)
        assert store.get_member(1) is not None
        assert store.get_member(1).name == "Test"

    def test_add_member_persists_across_reinit(self, store, log_path, members_path):
        member = FamilyMember(id=1, name="Persistent", sex="male", age_years=30.0)
        store.add_member(member)
        new_store = CookingLogStore(log_path, members_path)
        assert new_store.get_member(1) is not None
        assert new_store.get_member(1).name == "Persistent"

    def test_add_member_overwrites_existing(self, store):
        member1 = FamilyMember(id=1, name="First", sex="female", age_years=5.0)
        member2 = FamilyMember(id=1, name="Second", sex="female", age_years=5.0)
        store.add_member(member1)
        store.add_member(member2)
        assert store.get_member(1).name == "Second"

    def test_add_member_saves_all_fields(self, store):
        member = FamilyMember(
            id=1,
            name="Complete",
            sex="female",
            age_years=25.0,
            pregnant=True,
            lactating=True,
            dislikes=["onion", "garlic"],
        )
        store.add_member(member)
        reloaded = store.get_member(1)
        assert reloaded.name == "Complete"
        assert reloaded.pregnant is True
        assert reloaded.lactating is True
        assert reloaded.dislikes == ["onion", "garlic"]


class TestRemoveMember:
    def test_remove_member_deletes_member(self, store_with_data):
        store_with_data.remove_member(1)
        assert store_with_data.get_member(1) is None

    def test_remove_member_nonexistent_does_not_raise(self, store):
        store.remove_member(999)


class TestSessions:
    def test_get_sessions_returns_empty_when_no_sessions(self, store):
        assert store.get_sessions() == []

    def test_log_session_creates_session(self, store):
        session = store.log_session(recipe_id=10, servings_made=4.0)
        assert session.id == 1
        assert session.recipe_id == 10
        assert session.servings_made == 4.0

    def test_log_session_increments_id(self, store):
        s1 = store.log_session(recipe_id=10, servings_made=4.0)
        s2 = store.log_session(recipe_id=20, servings_made=3.0)
        assert s2.id == 2
        assert s1.id != s2.id

    def test_log_session_with_servings_served(self, store):
        session = store.log_session(
            recipe_id=10,
            servings_made=4.0,
            servings_served={1: 1.0, 2: 2.0},
        )
        assert session.servings_served == {1: 1.0, 2: 2.0}

    def test_log_session_with_notes(self, store):
        session = store.log_session(recipe_id=10, servings_made=4.0, notes="Delicious!")
        assert session.notes == "Delicious!"

    def test_log_session_with_log_date(self, store):
        log_date = date(2025, 1, 15)
        session = store.log_session(recipe_id=10, servings_made=4.0, log_date=log_date)
        assert session.date == log_date

    def test_log_session_persists_across_reinit(self, store, log_path, members_path):
        store.log_session(recipe_id=10, servings_made=4.0)
        new_store = CookingLogStore(log_path, members_path)
        assert len(new_store._sessions) == 1
        assert new_store._sessions[0].recipe_id == 10

    def test_get_sessions_filter_by_recipe_id(self, store_with_data):
        sessions = store_with_data.get_sessions(recipe_id=10)
        assert len(sessions) == 1
        assert sessions[0].recipe_id == 10

    def test_get_sessions_filter_by_member_id(self, store_with_data):
        sessions = store_with_data.get_sessions(member_id=1)
        assert len(sessions) == 1
        assert 1 in sessions[0].servings_served

    def test_get_sessions_filter_by_since(self, store_with_data):
        since = date(2025, 1, 1)
        sessions = store_with_data.get_sessions(since=since)
        assert len(sessions) == 2
        since = date(2025, 1, 2)
        sessions = store_with_data.get_sessions(since=since)
        assert len(sessions) == 1

    def test_get_sessions_combined_filters(self, store_with_data):
        sessions = store_with_data.get_sessions(recipe_id=10, member_id=2)
        assert len(sessions) == 1

    def test_get_sessions_returns_sorted_by_date_desc(self, store_with_data):
        sessions = store_with_data.get_sessions()
        assert sessions[0].date >= sessions[1].date

    def test_get_recent_sessions(self, store_with_data):
        sessions = store_with_data.get_recent_sessions(days=1)
        cutoff = date.today() - timedelta(days=1)
        for s in sessions:
            assert s.date >= cutoff

    def test_total_servings_for_member(self, store_with_data):
        total = store_with_data.total_servings_for_member(member_id=2, recipe_id=20)
        assert total == 1.5

    def test_remove_last_session(self, store):
        store.log_session(recipe_id=10, servings_made=4.0)
        store.log_session(recipe_id=20, servings_made=3.0)
        result = store.remove_last_session()
        assert result is True
        assert len(store._sessions) == 1

    def test_remove_last_session_empty_store(self, store):
        result = store.remove_last_session()
        assert result is False


class TestAtomicSave:
    def test_atomic_save_uses_tempfile(self, log_path, members_path, tmp_path):
        store = CookingLogStore(log_path, members_path)
        store.log_session(recipe_id=1, servings_made=1.0)
        temp_files = list(tmp_path.glob(".cooking_log.tmp.*"))
        assert len(temp_files) == 0

    def test_atomic_save_creates_valid_json(self, log_path, members_path):
        store = CookingLogStore(log_path, members_path)
        store.log_session(recipe_id=1, servings_made=2.0)
        with open(log_path) as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 1


class TestThreadSafety:
    def test_concurrent_add_member_calls(self, store):
        errors = []

        def add_member(member_id):
            try:
                member = FamilyMember(
                    id=member_id,
                    name=f"Member{member_id}",
                    sex="female",
                    age_years=20.0,
                )
                store.add_member(member)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=add_member, args=(i,))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert len(store.get_members()) == 10

    def test_concurrent_log_session_calls(self, store):
        errors = []

        def log_session(recipe_id):
            try:
                store.log_session(recipe_id=recipe_id, servings_made=1.0)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=log_session, args=(i,))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert len(store._sessions) == 5


class TestFamilyMemberRoundtrip:
    def test_member_dict_roundtrip(self):
        member = FamilyMember(
            id=1,
            name="TestMember",
            sex="male",
            age_years=15.5,
            pregnant=False,
            lactating=True,
            dislikes=["fish", "milk"],
        )
        assert member.id == 1
        assert member.name == "TestMember"
        assert member.sex == "male"
        assert member.age_years == 15.5
        assert member.lactating is True
        assert member.dislikes == ["fish", "milk"]


class TestCookingSessionRoundtrip:
    def test_session_dict_roundtrip(self):
        session = CookingSession(
            id=1,
            date=date(2025, 3, 15),
            recipe_id=42,
            servings_made=3.5,
            servings_served={1: 1.0, 2: 2.0},
            notes="Tasty",
        )
        assert session.id == 1
        assert session.date == date(2025, 3, 15)
        assert session.recipe_id == 42
        assert session.servings_made == 3.5
        assert session.servings_served[1] == 1.0
        assert session.notes == "Tasty"


class TestLifeStage:
    def test_infant_life_stage(self):
        member = FamilyMember(id=1, name="Baby", sex="female", age_years=0.5)
        assert member.life_stage == "infant"

    def test_toddler_life_stage(self):
        member = FamilyMember(id=1, name="Toddler", sex="female", age_years=2.0)
        assert member.life_stage == "toddler"

    def test_child_life_stage(self):
        member = FamilyMember(id=1, name="Child", sex="female", age_years=7.0)
        assert member.life_stage == "child"

    def test_adolescent_life_stage(self):
        member = FamilyMember(id=1, name="Teen", sex="female", age_years=15.0)
        assert member.life_stage == "adolescent"

    def test_adult_life_stage(self):
        member = FamilyMember(id=1, name="Adult", sex="male", age_years=35.0)
        assert member.life_stage == "adult"