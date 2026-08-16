"""Tests for Telegram command registration in the bot.

Guards against the startup crash caused by registering a command name that
python-telegram-bot rejects (e.g. ``balance-family`` with a hyphen — Telegram
commands may only contain lowercase ASCII letters, digits and underscores).
"""
import importlib
import re
import string

from telegram.ext import CommandHandler

import recepti.bot as bot

_VALID_CHARS = set(string.ascii_lowercase + string.digits + "_")


def _registered_command_names() -> list[str]:
    """Extract every command name passed to CommandHandler in the bot module."""
    src = importlib.util.spec_from_file_location(
        "recepti_bot_src", bot.__file__
    ).loader.get_source("recepti_bot_src")
    return re.findall(r'CommandHandler\(\s*"([^"]+)"', src)


def test_all_registered_commands_are_valid_telegram_names():
    """No registered command may crash Application.add_handler at startup."""
    for name in _registered_command_names():
        assert isinstance(name, str) and name, "empty command name in bot.py"
        assert all(ch in _VALID_CHARS for ch in name), (
            f"command {name!r} contains chars invalid for a Telegram bot command "
            f"(only lowercase a-z, 0-9, _ allowed)"
        )


def test_every_registered_command_registers_without_error():
    """Reproduce the main() registration path: add_handler must not raise."""
    app = bot.Application.builder().token("0000:test").build()
    for name in _registered_command_names():
        # CommandHandler() itself raises for invalid names; building + adding
        # mirrors what main() does and is what crashed on `balance-family`.
        handler = CommandHandler(name, bot.help_command)
        app.add_handler(handler)


def test_balance_family_uses_underscore_not_hyphen():
    """Regression: /balance_family must be registered (not the invalid hyphen form)."""
    names = _registered_command_names()
    assert "balance_family" in names
    assert "balance-family" not in names
