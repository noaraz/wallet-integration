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


# Phase 02 replaces the photo-handler stub; see
# tests/unit/handlers/test_photo_handler.py for the full extract-and-render flow.


async def test_start_explains_multi_ticket_flow(fake_client) -> None:
    from wallet_bot.handlers.start_handler import handle_start

    await handle_start(42, fake_client)
    text = fake_client.sent[0][1].lower()
    assert "wallet" in text
    assert "ticket" in text
    assert any(kw in text for kw in ("more ticket", "bundle", "get wallet link", "tap"))


async def test_help_explains_multi_ticket_flow(fake_client) -> None:
    from wallet_bot.handlers.help_handler import handle_help

    await handle_help(42, fake_client)
    text = fake_client.sent[0][1].lower()
    assert "wallet" in text
    assert "ticket" in text
    assert any(kw in text for kw in ("multiple", "bundle", "more ticket", "get wallet link"))
