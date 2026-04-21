"""Tests for TelegramClientProtocol and TelegramClient."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock


def test_protocol_has_send_text_with_correct_signature() -> None:
    """TelegramClientProtocol must expose send_text(chat_id, text)."""
    from wallet_bot.services.telegram_client import TelegramClientProtocol

    assert hasattr(TelegramClientProtocol, "send_text")
    sig = inspect.signature(TelegramClientProtocol.send_text)
    params = list(sig.parameters)
    assert "chat_id" in params
    assert "text" in params


async def test_telegram_client_send_text_calls_bot_send_message() -> None:
    """TelegramClient.send_text must delegate to bot.send_message with correct args."""
    from wallet_bot.services.telegram_client import TelegramClient

    bot = MagicMock()
    bot.send_message = AsyncMock()
    client = TelegramClient(bot)

    await client.send_text(chat_id=42, text="hello")

    bot.send_message.assert_called_once_with(chat_id=42, text="hello")
