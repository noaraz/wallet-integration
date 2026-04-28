"""Application settings — single source of truth for all config."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import SecretStr, field_validator
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


def _split_ids(raw: str) -> list[int]:
    """Parse comma-separated integers; returns empty list for blank input."""
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


class _EnvWithCommaIds(EnvSettingsSource):
    """EnvSettingsSource that handles comma-separated list env vars
    (ALLOWED_TG_USER_IDS, WALLET_ORIGINS) as plain strings, bypassing
    pydantic-settings' JSON-decode for list fields."""

    def prepare_field_value(
        self,
        field_name: str,
        field: Any,
        value: Any,
        value_is_complex: bool,
    ) -> Any:
        if field_name == "allowed_tg_user_ids" and isinstance(value, str):
            # Return the parsed list (possibly empty); field_validator below
            # will raise ValidationError for the empty case.
            return _split_ids(value)
        if field_name == "wallet_origins" and isinstance(value, str):
            return [x.strip() for x in value.split(",") if x.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    bot_token: SecretStr  # env: BOT_TOKEN
    webhook_secret: SecretStr  # env: WEBHOOK_SECRET
    allowed_tg_user_ids: list[int]  # env: ALLOWED_TG_USER_IDS (comma-separated)
    gemini_api_key: SecretStr  # env: GEMINI_API_KEY (https://aistudio.google.com/app/apikey)
    gemini_model: str = (
        "gemini-2.5-flash"  # env: GEMINI_MODEL — override to ride out capacity outages
    )
    wallet_issuer_id: str = ""  # env: WALLET_ISSUER_ID
    wallet_sa_json: SecretStr | None = None  # env: WALLET_SA_JSON (full SA JSON; local dev only)
    wallet_origins: list[str] = []  # env: WALLET_ORIGINS (comma-separated)

    @field_validator("allowed_tg_user_ids")
    @classmethod
    def _ids_not_empty(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("ALLOWED_TG_USER_IDS must not be empty")
        return v

    model_config = SettingsConfigDict(env_file=".env")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            _EnvWithCommaIds(
                settings_cls
            ),  # replaces default env_settings to intercept list fields
            dotenv_settings,
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


class GeminiSettings(BaseSettings):
    """Stripped-down settings for ad-hoc Gemini-only tools (e.g.
    ``scripts/eval_ocr.py``).

    Exists so CLI tools can load just the Gemini env vars without forcing
    the operator to set ``BOT_TOKEN`` / ``WEBHOOK_SECRET`` etc. that are
    only relevant when running the bot. Centralises env access in
    ``config.py`` per the root CLAUDE.md rule (no ``os.environ`` outside
    this module).
    """

    gemini_api_key: SecretStr  # env: GEMINI_API_KEY
    gemini_model: str = "gemini-2.5-flash"  # env: GEMINI_MODEL

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
