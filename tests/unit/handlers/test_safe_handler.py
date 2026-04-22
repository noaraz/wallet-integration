"""Tests for the @safe_handler decorator (generic error replies + log on failure)."""

from __future__ import annotations

import logging

import pytest

from wallet_bot.handlers._safe import GENERIC_ERROR_REPLY, safe_handler
from wallet_bot.services.telegram_client import TelegramClientProtocol


class _FakeClient(TelegramClientProtocol):  # type: ignore[misc]
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_text(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))

    # Unused in this test — stubs to satisfy the protocol.
    async def send_with_inline_keyboard(self, chat_id, text, rows): ...  # type: ignore[no-untyped-def]
    async def edit_message_text(self, chat_id, message_id, text, rows): ...  # type: ignore[no-untyped-def]
    async def answer_callback_query(self, callback_query_id): ...  # type: ignore[no-untyped-def]
    async def send_force_reply(self, chat_id, text): ...  # type: ignore[no-untyped-def]
    async def download_photo_bytes(self, file_id): ...  # type: ignore[no-untyped-def]


async def test_safe_handler_runs_wrapped_fn_when_no_exception() -> None:
    client = _FakeClient()
    calls: list[int] = []

    @safe_handler
    async def ok(chat_id: int, client: TelegramClientProtocol) -> None:
        calls.append(chat_id)

    await ok(42, client)
    assert calls == [42]
    assert client.sent == []


async def test_safe_handler_swallows_exception_and_replies_generically(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _FakeClient()
    sensitive = "API_KEY=sk-abc123 leaked secret"

    @safe_handler
    async def broken(chat_id: int, client: TelegramClientProtocol) -> None:
        raise RuntimeError(sensitive)

    with caplog.at_level(logging.ERROR):
        await broken(42, client)

    # Generic reply to user — no exception detail leaks.
    assert client.sent == [(42, GENERIC_ERROR_REPLY)]
    assert "sk-abc123" not in " ".join(
        r.message for r in caplog.records if r.levelno < logging.ERROR
    )

    # Server-side log captured the exception via logger.exception.
    assert any("handler failed" in r.message.lower() for r in caplog.records)


async def test_safe_handler_never_raises() -> None:
    client = _FakeClient()

    @safe_handler
    async def broken(chat_id: int, client: TelegramClientProtocol) -> None:
        raise RuntimeError("boom")

    # Must not propagate — FastAPI should always see a clean return.
    await broken(1, client)


async def test_safe_handler_reply_failure_does_not_propagate() -> None:
    class ExplodingClient(_FakeClient):
        async def send_text(self, chat_id: int, text: str) -> None:
            raise RuntimeError("telegram down")

    client = ExplodingClient()

    @safe_handler
    async def broken(chat_id: int, client: TelegramClientProtocol) -> None:
        raise RuntimeError("primary")

    # Even if the fallback reply fails, the decorator must swallow it.
    await broken(1, client)
