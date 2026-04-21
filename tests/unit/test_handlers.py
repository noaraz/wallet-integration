"""Unit tests for update handlers."""

from __future__ import annotations

import pytest
from telegram import Update

_USER_ID = 111222333
_CHAT_ID = 111222333


def _make_update(data: dict) -> Update:
    return Update.de_json(data, None)  # type: ignore[arg-type]


def _command_update(text: str, user_id: int = _USER_ID) -> Update:
    return _make_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 1700000000,
                "chat": {"id": user_id, "type": "private"},
                "from": {"id": user_id, "is_bot": False, "first_name": "Test"},
                "text": text,
                "entities": [{"offset": 0, "length": len(text), "type": "bot_command"}],
            },
        }
    )


def _photo_update(user_id: int = _USER_ID) -> Update:
    return _make_update(
        {
            "update_id": 2,
            "message": {
                "message_id": 2,
                "date": 1700000000,
                "chat": {"id": user_id, "type": "private"},
                "from": {"id": user_id, "is_bot": False, "first_name": "Test"},
                "photo": [
                    {
                        "file_id": "AABB",
                        "file_unique_id": "CCDD",
                        "width": 100,
                        "height": 100,
                        "file_size": 1024,
                    }
                ],
            },
        }
    )


@pytest.mark.asyncio
async def test_start_sends_welcome(fake_client):
    from wallet_bot.handlers.start_handler import handle_start

    await handle_start(_command_update("/start"), fake_client)

    assert len(fake_client.sent) == 1
    chat_id, text = fake_client.sent[0]
    assert chat_id == _CHAT_ID
    assert "welcome" in text.lower() or "wallet" in text.lower()


@pytest.mark.asyncio
async def test_help_sends_help_text(fake_client):
    from wallet_bot.handlers.help_handler import handle_help

    await handle_help(_command_update("/help"), fake_client)

    assert len(fake_client.sent) == 1
    chat_id, text = fake_client.sent[0]
    assert chat_id == _CHAT_ID
    assert "/start" in text or "/help" in text


@pytest.mark.asyncio
async def test_photo_sends_processing_ack(fake_client):
    from wallet_bot.handlers.photo_handler import handle_photo

    await handle_photo(_photo_update(), fake_client)

    assert len(fake_client.sent) == 1
    chat_id, text = fake_client.sent[0]
    assert chat_id == _CHAT_ID
    assert "processing" in text.lower()
