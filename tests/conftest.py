"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from wallet_bot.services.telegram_client import TelegramClientProtocol


class FakeClient(TelegramClientProtocol):  # type: ignore[misc]
    """Test double for TelegramClientProtocol — records send_text calls."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_text(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient()


_WEBHOOK_SECRET = "test-webhook-secret"
_BOT_TOKEN = "123456:fake_token_for_tests"
_ALLOWED_USER_ID = 111222333


@pytest.fixture(autouse=False)
def test_env(monkeypatch):
    """Patch env vars and clear settings cache before each test that needs the app."""
    monkeypatch.setenv("BOT_TOKEN", _BOT_TOKEN)
    monkeypatch.setenv("WEBHOOK_SECRET", _WEBHOOK_SECRET)
    monkeypatch.setenv("ALLOWED_TG_USER_IDS", str(_ALLOWED_USER_ID))
    from wallet_bot.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def test_app(test_env, fake_client):
    """FastAPI app with lifespan running and client dependency overridden."""
    from wallet_bot.main import app, get_client

    app.dependency_overrides[get_client] = lambda: fake_client
    try:
        async with (
            LifespanManager(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
        ):
            yield client
    finally:
        app.dependency_overrides.clear()
