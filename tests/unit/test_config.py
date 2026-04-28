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


def test_gemini_model_defaults_to_2_5_flash(monkeypatch):
    _make(monkeypatch)
    s = Settings(_env_file=None)
    assert s.gemini_model == "gemini-2.5-flash"


def test_gemini_model_override_from_env(monkeypatch):
    _make(monkeypatch)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-flash-latest")
    s = Settings(_env_file=None)
    assert s.gemini_model == "gemini-flash-latest"


def test_gemini_only_settings_does_not_require_bot_vars(monkeypatch):
    """Eval/CLI tools (scripts/eval_ocr.py) should be able to load just
    Gemini config without forcing the user to set BOT_TOKEN etc.
    Keeps env-var access inside config.py per CLAUDE.md."""
    from wallet_bot.config import GeminiSettings

    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("ALLOWED_TG_USER_IDS", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "abc-123")

    s = GeminiSettings(_env_file=None)
    assert s.gemini_api_key.get_secret_value() == "abc-123"
    assert s.gemini_model == "gemini-2.5-flash"


def test_gemini_only_settings_honours_model_override(monkeypatch):
    from wallet_bot.config import GeminiSettings

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-flash-latest")

    s = GeminiSettings(_env_file=None)
    assert s.gemini_model == "gemini-flash-latest"


def test_wallet_config_defaults(monkeypatch):
    """Wallet fields are optional — existing envs don't break."""
    _make(monkeypatch)
    s = Settings(_env_file=None)
    assert s.wallet_issuer_id == ""
    assert s.wallet_sa_json is None
    assert s.wallet_origins == []


def test_wallet_config_from_env(monkeypatch):
    _make(monkeypatch)
    monkeypatch.setenv("WALLET_ISSUER_ID", "3388000000012345678")
    monkeypatch.setenv("WALLET_SA_JSON", '{"type":"service_account"}')
    monkeypatch.setenv("WALLET_ORIGINS", "https://example.com,https://bot.example.com")
    s = Settings(_env_file=None)
    assert s.wallet_issuer_id == "3388000000012345678"
    assert s.wallet_sa_json is not None
    assert s.wallet_sa_json.get_secret_value() == '{"type":"service_account"}'
    assert '{"type":"service_account"}' not in repr(s)
    assert s.wallet_origins == ["https://example.com", "https://bot.example.com"]
