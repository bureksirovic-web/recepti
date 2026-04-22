"""Tests for CuisineBlacklister."""

from unittest.mock import MagicMock, call

import pytest

from recepti.cuisine_blacklister import CuisineBlacklister


@pytest.fixture
def blacklister(tmp_path):
    mock_cooking_log = MagicMock()
    mock_ratings = MagicMock()
    mock_recipes = MagicMock()
    return CuisineBlacklister(mock_cooking_log, mock_ratings, mock_recipes, threshold=3)


class TestSync:
    def test_sync_adds_cuisine_to_member_dislikes(self, blacklister):
        member = MagicMock()
        member.dislikes = []
        blacklister.cooking_log.get_members.return_value = [member]
        blacklister.ratings.get_rejected_cuisines.return_value = {"punjabi": 3}

        result = blacklister.sync()

        assert "punjabi" in member.dislikes

    def test_sync_does_not_duplicate_cuisine(self, blacklister):
        member = MagicMock()
        member.dislikes = ["punjabi"]
        blacklister.cooking_log.get_members.return_value = [member]
        blacklister.ratings.get_rejected_cuisines.return_value = {"punjabi": 3}

        blacklister.sync()

        assert member.dislikes.count("punjabi") == 1

    def test_sync_calls_add_member_when_changed(self, blacklister):
        member = MagicMock()
        member.dislikes = []
        blacklister.cooking_log.get_members.return_value = [member]
        blacklister.ratings.get_rejected_cuisines.return_value = {"punjabi": 3}

        blacklister.sync()

        blacklister.cooking_log.add_member.assert_called_once_with(member)

    def test_sync_does_not_call_add_member_when_no_change(self, blacklister):
        member = MagicMock()
        member.dislikes = ["punjabi"]
        blacklister.cooking_log.get_members.return_value = [member]
        blacklister.ratings.get_rejected_cuisines.return_value = {"punjabi": 3}

        blacklister.sync()

        blacklister.cooking_log.add_member.assert_not_called()

    def test_sync_returns_newly_blacklisted(self, blacklister):
        member1 = MagicMock()
        member1.dislikes = []
        member2 = MagicMock()
        member2.dislikes = []
        blacklister.cooking_log.get_members.return_value = [member1, member2]
        blacklister.ratings.get_rejected_cuisines.return_value = {"punjabi": 3, "croatian": 4}

        result = blacklister.sync()

        assert result["punjabi"] == 6
        assert result["croatian"] == 8

    def test_sync_returns_empty_when_no_rejections(self, blacklister):
        member = MagicMock()
        member.dislikes = []
        blacklister.cooking_log.get_members.return_value = [member]
        blacklister.ratings.get_rejected_cuisines.return_value = {}

        result = blacklister.sync()

        assert result == {}

    def test_sync_returns_empty_when_all_already_blacklisted(self, blacklister):
        member = MagicMock()
        member.dislikes = ["punjabi", "croatian"]
        blacklister.cooking_log.get_members.return_value = [member]
        blacklister.ratings.get_rejected_cuisines.return_value = {"punjabi": 3, "croatian": 4}

        result = blacklister.sync()

        assert result == {}

    def test_sync_multiple_members(self, blacklister):
        member1 = MagicMock()
        member1.dislikes = []
        member2 = MagicMock()
        member2.dislikes = []
        blacklister.cooking_log.get_members.return_value = [member1, member2]
        blacklister.ratings.get_rejected_cuisines.return_value = {"punjabi": 3}

        result = blacklister.sync()

        assert "punjabi" in member1.dislikes
        assert "punjabi" in member2.dislikes
        assert result["punjabi"] == 6

    def test_sync_uses_threshold_from_init(self, blacklister):
        blacklister.ratings.get_rejected_cuisines.return_value = {}
        blacklister.sync()
        blacklister.ratings.get_rejected_cuisines.assert_called_once()
        call_args = blacklister.ratings.get_rejected_cuisines.call_args
        assert call_args[0][1] == 3

    def test_sync_empty_members(self, blacklister):
        blacklister.cooking_log.get_members.return_value = []
        blacklister.ratings.get_rejected_cuisines.return_value = {"punjabi": 3}

        result = blacklister.sync()

        assert result == {}