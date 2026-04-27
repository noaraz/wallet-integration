"""Webhook-level tests for Phase 02 routes: photo, callback_query, edit-reply, DM-only."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from wallet_bot.models.ticket import ExtractedTicket
from wallet_bot.services.vision_service import VisionExtractionError

_SECRET = "test-webhook-secret"
_ALLOWED_ID = 111222333
_CHAT_ID = _ALLOWED_ID


def _headers() -> dict[str, str]:
    return {"X-Telegram-Bot-Api-Secret-Token": _SECRET}


def _photo_update(chat_type: str = "private") -> dict:
    return {
        "update_id": 10,
        "message": {
            "message_id": 1,
            "date": 1700000000,
            "chat": {"id": _CHAT_ID, "type": chat_type},
            "from": {"id": _ALLOWED_ID, "is_bot": False, "first_name": "N"},
            "photo": [
                {"file_id": "FILE_SM", "file_unique_id": "U_SM", "width": 90, "height": 90},
                {"file_id": "FILE_LG", "file_unique_id": "U_LG", "width": 1280, "height": 1280},
            ],
        },
    }


def _callback_update(data: str, chat_type: str = "private") -> dict:
    return {
        "update_id": 11,
        "callback_query": {
            "id": "cb-abc",
            "from": {"id": _ALLOWED_ID, "is_bot": False, "first_name": "N"},
            "chat_instance": "xyz",
            "message": {
                "message_id": 7,
                "date": 1700000000,
                "chat": {"id": _CHAT_ID, "type": chat_type},
                "from": {"id": 0, "is_bot": True, "first_name": "Bot"},
                "text": "draft",
            },
            "data": data,
        },
    }


def _text_update(text: str, chat_type: str = "private") -> dict:
    return {
        "update_id": 12,
        "message": {
            "message_id": 3,
            "date": 1700000000,
            "chat": {"id": _CHAT_ID, "type": chat_type},
            "from": {"id": _ALLOWED_ID, "is_bot": False, "first_name": "N"},
            "text": text,
        },
    }


@pytest.fixture
def patched_vision(monkeypatch):
    """Patch the vision-service factory so the webhook uses a controllable fake."""
    fake = AsyncMock()
    fake.extract = AsyncMock(return_value=ExtractedTicket(event_name="גיא מזיג"))
    monkeypatch.setattr(
        "wallet_bot.main.create_default_service",
        lambda *a, **kw: fake,
    )
    return fake


async def test_photo_runs_extraction_and_sends_keyboard(
    test_app, fake_client, patched_vision
) -> None:
    resp = await test_app.post("/telegram/webhook", json=_photo_update(), headers=_headers())
    assert resp.status_code == 200

    # Largest PhotoSize used.
    assert fake_client.downloaded == ["FILE_LG"]
    patched_vision.extract.assert_called_once()
    assert len(fake_client.sent_with_keyboard) == 1


async def test_callback_query_routes_to_callback_handler(
    test_app, fake_client, patched_vision
) -> None:
    # First, send a photo so a draft exists.
    await test_app.post("/telegram/webhook", json=_photo_update(), headers=_headers())

    resp = await test_app.post(
        "/telegram/webhook",
        json=_callback_update("cancel"),
        headers=_headers(),
    )
    assert resp.status_code == 200
    assert fake_client.answered == ["cb-abc"]
    assert any("cancel" in text.lower() for _, text in fake_client.sent)


async def test_text_during_edit_mode_applies_to_draft(
    test_app, fake_client, patched_vision
) -> None:
    # 1. Photo establishes draft.
    await test_app.post("/telegram/webhook", json=_photo_update(), headers=_headers())
    # 2. Tap Edit Event to enter edit-mode.
    await test_app.post(
        "/telegram/webhook",
        json=_callback_update("edit_event_name"),
        headers=_headers(),
    )
    # 3. Text reply: the corrected event name.
    resp = await test_app.post(
        "/telegram/webhook",
        json=_text_update("גיא מזיג המתוקן"),
        headers=_headers(),
    )
    assert resp.status_code == 200

    # Draft message was edited with the new value.
    assert any("המתוקן" in text for (_, _, text, _) in fake_client.edited)


async def test_group_chat_photo_is_rejected_with_dm_only_reply(
    test_app, fake_client, patched_vision
) -> None:
    resp = await test_app.post(
        "/telegram/webhook",
        json=_photo_update(chat_type="group"),
        headers=_headers(),
    )
    assert resp.status_code == 200
    # Vision never invoked.
    patched_vision.extract.assert_not_called()
    # One-shot DM-only reply.
    assert any("dm" in text.lower() or "private" in text.lower() for _, text in fake_client.sent)


async def test_group_chat_callback_acks_query_and_drops_silently(
    test_app, fake_client, patched_vision
) -> None:
    """A forwarded keyboard message tapped in a group must NOT leave the
    Telegram button spinner running. Even when we drop the callback (we
    only support DMs), we must answer_callback_query first."""
    bad = _callback_update("edit_event_name", chat_type="group")
    resp = await test_app.post("/telegram/webhook", json=bad, headers=_headers())
    assert resp.status_code == 200
    # Query must be acked (spinner stops) even though we won't process it.
    assert "cb-abc" in fake_client.answered
    # No downstream side effects (no draft mutation, no force_reply, no edit).
    assert fake_client.force_replies == []
    assert fake_client.edited == []


async def test_unknown_callback_data_is_dropped_safely(
    test_app, fake_client, patched_vision
) -> None:
    await test_app.post("/telegram/webhook", json=_photo_update(), headers=_headers())

    resp = await test_app.post(
        "/telegram/webhook",
        json=_callback_update("edit_../../secret"),
        headers=_headers(),
    )
    assert resp.status_code == 200
    # Spinner stopped but no edit / force-reply / text sent for the malicious cb.
    assert "cb-abc" in fake_client.answered
    assert fake_client.force_replies == []


async def test_vision_error_surfaces_generic_reply(test_app, fake_client, patched_vision) -> None:
    patched_vision.extract = AsyncMock(side_effect=VisionExtractionError("backend down"))

    resp = await test_app.post("/telegram/webhook", json=_photo_update(), headers=_headers())
    assert resp.status_code == 200
    assert fake_client.sent_with_keyboard == []
    assert any("something went wrong" in text.lower() for _, text in fake_client.sent)


async def test_non_whitelisted_user_callback_returns_403(test_app, patched_vision) -> None:
    bad = _callback_update("cancel")
    bad["callback_query"]["from"]["id"] = 999_999_999
    bad["callback_query"]["message"]["chat"]["id"] = 999_999_999
    resp = await test_app.post("/telegram/webhook", json=bad, headers=_headers())
    assert resp.status_code == 403
