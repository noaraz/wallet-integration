"""Tests for Settings validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from wallet_bot.config import Settings


def _make(
    monkeypatch,
    *,
    bot_token="tok",
    webhook_secret="sec",
    allowed="111",
    gemini_key="gemini-key",
):
    monkeypatch.setenv("BOT_TOKEN", bot_token)
    monkeypatch.setenv("WEBHOOK_SECRET", webhook_secret)
    monkeypatch.setenv("ALLOWED_TG_USER_IDS", allowed)
    monkeypatch.setenv("GEMINI_API_KEY", gemini_key)


def test_missing_bot_token(monkeypatch):
    _make(monkeypatch)
    monkeypatch.delenv("BOT_TOKEN")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_missing_webhook_secret(monkeypatch):
    _make(monkeypatch)
    monkeypatch.delenv("WEBHOOK_SECRET")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_empty_allowed_ids_raises(monkeypatch):
    _make(monkeypatch, allowed="")
    with pytest.raises(ValidationError, match="ALLOWED_TG_USER_IDS must not be empty"):
        Settings(_env_file=None)


def test_comma_separated_ids_parsed(monkeypatch):
    _make(monkeypatch, allowed="123,456")
    s = Settings(_env_file=None)
    assert s.allowed_tg_user_ids == [123, 456]


def test_single_id_parsed(monkeypatch):
    _make(monkeypatch, allowed="789")
    s = Settings(_env_file=None)
    assert s.allowed_tg_user_ids == [789]


def test_ids_with_spaces_parsed(monkeypatch):
    _make(monkeypatch, allowed="123 , 456 ")
    s = Settings(_env_file=None)
    assert s.allowed_tg_user_ids == [123, 456]


def test_missing_gemini_api_key(monkeypatch):
    _make(monkeypatch)
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_gemini_api_key_is_secret(monkeypatch):
    _make(monkeypatch, gemini_key="super-secret-123")
    s = Settings(_env_file=None)
    # SecretStr repr must not leak the value.
    assert "super-secret-123" not in repr(s)
    assert s.gemini_api_key.get_secret_value() == "super-secret-123"
