"""Unit tests for update handlers."""

from __future__ import annotations

_CHAT_ID = 111222333


async def test_start_sends_welcome(fake_client):
    from wallet_bot.handlers.start_handler import handle_start

    await handle_start(_CHAT_ID, fake_client)

    assert len(fake_client.sent) == 1
    chat_id, text = fake_client.sent[0]
    assert chat_id == _CHAT_ID
    assert "welcome" in text.lower() or "wallet" in text.lower()


async def test_help_sends_help_text(fake_client):
    from wallet_bot.handlers.help_handler import handle_help

    await handle_help(_CHAT_ID, fake_client)

    assert len(fake_client.sent) == 1
    chat_id, text = fake_client.sent[0]
    assert chat_id == _CHAT_ID
    assert "/start" in text or "/help" in text


async def test_photo_sends_processing_ack(fake_client):
    from wallet_bot.handlers.photo_handler import handle_photo

    await handle_photo(_CHAT_ID, fake_client)

    assert len(fake_client.sent) == 1
    chat_id, text = fake_client.sent[0]
    assert chat_id == _CHAT_ID
    assert "processing" in text.lower()
