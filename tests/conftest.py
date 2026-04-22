"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from wallet_bot.services.telegram_client import InlineButton, TelegramClientProtocol


class FakeClient(TelegramClientProtocol):  # type: ignore[misc]
    """Test double for TelegramClientProtocol — records every outbound call."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.sent_with_keyboard: list[tuple[int, str, list[list[InlineButton]]]] = []
        self.edited: list[tuple[int, int, str, list[list[InlineButton]]]] = []
        self.answered: list[str] = []
        self.force_replies: list[tuple[int, str]] = []
        self.downloaded: list[str] = []
        # Test-configurable: next message_id to return from send/force_reply.
        self.next_message_id: int = 1000
        # Test-configurable: bytes returned by download_photo_bytes.
        self.next_photo_bytes: bytes = b"\x89PNG fake"
        self.next_photo_mime: str = "image/jpeg"

    async def send_text(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))

    async def send_with_inline_keyboard(
        self,
        chat_id: int,
        text: str,
        rows: list[list[InlineButton]],
    ) -> int:
        self.sent_with_keyboard.append((chat_id, text, rows))
        mid = self.next_message_id
        self.next_message_id += 1
        return mid

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        rows: list[list[InlineButton]],
    ) -> None:
        self.edited.append((chat_id, message_id, text, rows))

    async def answer_callback_query(self, callback_query_id: str) -> None:
        self.answered.append(callback_query_id)

    async def send_force_reply(self, chat_id: int, text: str) -> int:
        self.force_replies.append((chat_id, text))
        mid = self.next_message_id
        self.next_message_id += 1
        return mid

    async def download_photo_bytes(self, file_id: str) -> tuple[bytes, str]:
        self.downloaded.append(file_id)
        return self.next_photo_bytes, self.next_photo_mime


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient()


_WEBHOOK_SECRET = "test-webhook-secret"
_BOT_TOKEN = "123456:fake_token_for_tests"
_ALLOWED_USER_ID = 111222333
_GEMINI_API_KEY = "test-gemini-key"


@pytest.fixture(autouse=False)
def test_env(monkeypatch):
    """Patch env vars and clear settings cache before each test that needs the app."""
    monkeypatch.setenv("BOT_TOKEN", _BOT_TOKEN)
    monkeypatch.setenv("WEBHOOK_SECRET", _WEBHOOK_SECRET)
    monkeypatch.setenv("ALLOWED_TG_USER_IDS", str(_ALLOWED_USER_ID))
    monkeypatch.setenv("GEMINI_API_KEY", _GEMINI_API_KEY)
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
