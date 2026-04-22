"""Tests for TelegramClientProtocol and TelegramClient."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock


def test_protocol_exposes_phase_02_methods() -> None:
    """Protocol must expose everything the Phase 02 handlers need."""
    from wallet_bot.services.telegram_client import TelegramClientProtocol

    for method in (
        "send_text",
        "send_with_inline_keyboard",
        "edit_message_text",
        "answer_callback_query",
        "send_force_reply",
        "download_photo_bytes",
    ):
        assert hasattr(TelegramClientProtocol, method), method


def test_send_text_signature() -> None:
    from wallet_bot.services.telegram_client import TelegramClientProtocol

    sig = inspect.signature(TelegramClientProtocol.send_text)
    params = list(sig.parameters)
    assert "chat_id" in params
    assert "text" in params


async def test_send_text_delegates_to_bot() -> None:
    from wallet_bot.services.telegram_client import TelegramClient

    bot = MagicMock()
    bot.send_message = AsyncMock()
    client = TelegramClient(bot)

    await client.send_text(chat_id=42, text="hello")

    bot.send_message.assert_called_once_with(chat_id=42, text="hello")


async def test_send_with_inline_keyboard_returns_message_id_and_forbids_markdown() -> None:
    from wallet_bot.services.telegram_client import InlineButton, TelegramClient

    bot = MagicMock()
    sent = MagicMock()
    sent.message_id = 777
    bot.send_message = AsyncMock(return_value=sent)
    client = TelegramClient(bot)

    rows = [
        [InlineButton(text="Edit Event", callback_data="edit_event_name")],
        [InlineButton(text="✅ Approve", callback_data="approve")],
    ]
    message_id = await client.send_with_inline_keyboard(chat_id=1, text="draft", rows=rows)
    assert message_id == 777

    kwargs = bot.send_message.call_args.kwargs
    assert kwargs["chat_id"] == 1
    assert kwargs["text"] == "draft"
    # Security: no Markdown/HTML parse_mode ever.
    assert kwargs.get("parse_mode") is None
    assert "reply_markup" in kwargs


async def test_edit_message_text_forbids_parse_mode() -> None:
    from wallet_bot.services.telegram_client import InlineButton, TelegramClient

    bot = MagicMock()
    bot.edit_message_text = AsyncMock()
    client = TelegramClient(bot)

    await client.edit_message_text(
        chat_id=1,
        message_id=77,
        text="new",
        rows=[[InlineButton(text="Cancel", callback_data="cancel")]],
    )
    kwargs = bot.edit_message_text.call_args.kwargs
    assert kwargs["chat_id"] == 1
    assert kwargs["message_id"] == 77
    assert kwargs["text"] == "new"
    assert kwargs.get("parse_mode") is None


async def test_answer_callback_query_delegates() -> None:
    from wallet_bot.services.telegram_client import TelegramClient

    bot = MagicMock()
    bot.answer_callback_query = AsyncMock()
    client = TelegramClient(bot)

    await client.answer_callback_query("abc123")
    bot.answer_callback_query.assert_called_once_with(callback_query_id="abc123")


async def test_send_force_reply_returns_message_id_and_forbids_markdown() -> None:
    from wallet_bot.services.telegram_client import TelegramClient

    bot = MagicMock()
    sent = MagicMock()
    sent.message_id = 42
    bot.send_message = AsyncMock(return_value=sent)
    client = TelegramClient(bot)

    message_id = await client.send_force_reply(chat_id=1, text="Type the new value")
    assert message_id == 42

    kwargs = bot.send_message.call_args.kwargs
    assert kwargs["chat_id"] == 1
    assert kwargs["text"] == "Type the new value"
    assert kwargs.get("parse_mode") is None
    assert "reply_markup" in kwargs


async def test_download_photo_bytes_returns_bytes_and_mime() -> None:
    from wallet_bot.services.telegram_client import TelegramClient

    bot = MagicMock()
    tg_file = MagicMock()

    async def _download() -> bytearray:
        return bytearray(b"\x89PNG fake")

    tg_file.download_as_bytearray = _download
    bot.get_file = AsyncMock(return_value=tg_file)
    client = TelegramClient(bot)

    data, mime = await client.download_photo_bytes(file_id="ABC")
    assert data == b"\x89PNG fake"
    assert mime == "image/jpeg"  # Telegram sends PhotoSize as JPEG
    bot.get_file.assert_called_once_with(file_id="ABC")
