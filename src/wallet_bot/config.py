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
    """EnvSettingsSource that treats ALLOWED_TG_USER_IDS as a plain string,
    bypassing pydantic-settings' JSON-decode for list fields."""

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
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    bot_token: SecretStr  # env: BOT_TOKEN
    webhook_secret: SecretStr  # env: WEBHOOK_SECRET
    allowed_tg_user_ids: list[int]  # env: ALLOWED_TG_USER_IDS (comma-separated)
    gemini_api_key: SecretStr  # env: GEMINI_API_KEY (https://aistudio.google.com/app/apikey)
    gemini_model: str = (
        "gemini-2.5-flash"  # env: GEMINI_MODEL — override to ride out capacity outages
    )

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
