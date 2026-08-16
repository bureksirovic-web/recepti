"""Tests for the kuhano_command Telegram handler."""

import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from recepti.bot import kuhano_command


def _run_async(coro) -> None:
    """Run ``coro`` even if a stale event loop is left running on the main
    thread (e.g. by the pytest-playwright e2e session). ``asyncio.run`` refuses
    to be called from a running loop, so fall back to a fresh loop on a
    dedicated thread. Each kuhano handler coroutine is fully independent, so
    this is safe."""
    try:
        asyncio.run(coro)
    except RuntimeError as exc:
        if "running event loop" not in str(exc):
            raise
        result: dict = {}

        def _target() -> None:
            result["exc"] = None
            try:
                asyncio.run(coro)
            except BaseException as e:  # pragma: no cover - propagates below
                result["exc"] = e

        t = threading.Thread(target=_target)
        t.start()
        t.join()
        if result.get("exc") is not None:
            raise result["exc"]


def make_update() -> MagicMock:
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    return update


def make_ctx(args: list[str]) -> MagicMock:
    ctx = MagicMock()
    ctx.args = args
    return ctx


@pytest.fixture
def mock_store():
    return patch("recepti.bot.get_store")


@pytest.fixture
def mock_cooking_log():
    return patch("recepti.bot.get_cooking_log")


class TestKuhanoCommand:
    async def _run(self, update, ctx):
        await kuhano_command(update, ctx)

    def test_no_args_replies_usage(self, mock_store, mock_cooking_log):
        update = make_update()
        ctx = make_ctx([])

        _run_async(self._run(update, ctx))

        update.message.reply_text.assert_called_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "Upotreba: /kuhano" in reply

    def test_invalid_recipe_id_replies_error(self, mock_store, mock_cooking_log):
        update = make_update()
        ctx = make_ctx(["notanumber"])

        _run_async(self._run(update, ctx))

        update.message.reply_text.assert_called_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "Ne mogu naći" in reply

    def test_recipe_not_found_replies_error(self, mock_store, mock_cooking_log):
        update = make_update()
        ctx = make_ctx(["99999"])

        with mock_store as ps, mock_cooking_log:
            ps.return_value.get_recipe_by_id.return_value = None

            _run_async(self._run(update, ctx))

        update.message.reply_text.assert_called_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "99999" in reply
        assert "ne postoji" in reply

    def test_valid_recipe_no_portions_uses_default(self, mock_store, mock_cooking_log):
        update = make_update()
        ctx = make_ctx(["42"])

        mock_recipe = MagicMock()
        mock_recipe.id = 42
        mock_recipe.name = "Paški makaruni"
        mock_recipe.servings = 4

        with mock_store as ps, mock_cooking_log as pl:
            ps.return_value.get_recipe_by_id.return_value = mock_recipe
            pl.return_value.log_session.return_value = MagicMock(id=1)

            _run_async(self._run(update, ctx))

            ps.return_value.get_recipe_by_id.assert_called_once_with(42)
            pl.return_value.log_session.assert_called_once()
            call_kwargs = pl.return_value.log_session.call_args.kwargs
            assert call_kwargs["recipe_id"] == 42
            assert call_kwargs["servings_made"] == 4.0

            update.message.reply_text.assert_called_once()
            reply = update.message.reply_text.call_args[0][0]
            assert "✅ Zapisano" in reply
            assert "Paški makaruni" in reply
            assert "4" in reply

    def test_valid_recipe_with_portions_uses_specified(self, mock_store, mock_cooking_log):
        update = make_update()
        ctx = make_ctx(["42", "6"])

        mock_recipe = MagicMock()
        mock_recipe.id = 42
        mock_recipe.name = "Paški makaruni"
        mock_recipe.servings = 4

        with mock_store as ps, mock_cooking_log as pl:
            ps.return_value.get_recipe_by_id.return_value = mock_recipe
            pl.return_value.log_session.return_value = MagicMock(id=1)

            _run_async(self._run(update, ctx))

            pl.return_value.log_session.assert_called_once()
            call_kwargs = pl.return_value.log_session.call_args.kwargs
            assert call_kwargs["servings_made"] == 6.0
            assert call_kwargs["recipe_id"] == 42

            reply = update.message.reply_text.call_args[0][0]
            assert "✅ Zapisano" in reply
            assert "6" in reply

    def test_zero_portions_replies_error(self, mock_store, mock_cooking_log):
        update = make_update()
        ctx = make_ctx(["42", "0"])

        mock_recipe = MagicMock()
        mock_recipe.name = "Paški makaruni"
        mock_recipe.servings = 4

        with mock_store as ps, mock_cooking_log as pl:
            ps.return_value.get_recipe_by_id.return_value = mock_recipe

            _run_async(self._run(update, ctx))

        update.message.reply_text.assert_called_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "Broj porcija mora biti pozitivan" in reply
        pl.return_value.log_session.assert_not_called()

    def test_negative_portions_replies_error(self, mock_store, mock_cooking_log):
        update = make_update()
        ctx = make_ctx(["42", "-3"])

        mock_recipe = MagicMock()
        mock_recipe.name = "Paški makaruni"
        mock_recipe.servings = 4

        with mock_store as ps, mock_cooking_log as pl:
            ps.return_value.get_recipe_by_id.return_value = mock_recipe

            _run_async(self._run(update, ctx))

        update.message.reply_text.assert_called_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "Broj porcija mora biti pozitivan" in reply
        pl.return_value.log_session.assert_not_called()

    def test_non_numeric_portions_fails_int_parse(self, mock_store, mock_cooking_log):
        update = make_update()
        ctx = make_ctx(["42", "abc"])

        mock_recipe = MagicMock()
        mock_recipe.name = "Paški makaruni"
        mock_recipe.servings = 4

        with mock_store as ps, mock_cooking_log as pl:
            ps.return_value.get_recipe_by_id.return_value = mock_recipe

            _run_async(self._run(update, ctx))

        update.message.reply_text.assert_called_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "Broj porcija mora biti pozitivan" in reply
        pl.return_value.log_session.assert_not_called()

    def test_float_portions_accepted(self, mock_store, mock_cooking_log):
        update = make_update()
        ctx = make_ctx(["42", "2.5"])

        mock_recipe = MagicMock()
        mock_recipe.name = "Paški makaruni"
        mock_recipe.servings = 4

        with mock_store as ps, mock_cooking_log as pl:
            ps.return_value.get_recipe_by_id.return_value = mock_recipe
            pl.return_value.log_session.return_value = MagicMock(id=1)

            _run_async(self._run(update, ctx))

            pl.return_value.log_session.assert_called_once()
            call_kwargs = pl.return_value.log_session.call_args.kwargs
            assert call_kwargs["servings_made"] == 2.5
