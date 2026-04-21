"""Tests for webhook endpoint authentication and routing."""

from __future__ import annotations

import pytest

_SECRET = "test-webhook-secret"
_ALLOWED_ID = 111222333
_BLOCKED_ID = 999999999

_START_UPDATE = {
    "update_id": 1,
    "message": {
        "message_id": 1,
        "date": 1700000000,
        "chat": {"id": _ALLOWED_ID, "type": "private"},
        "from": {"id": _ALLOWED_ID, "is_bot": False, "first_name": "Test"},
        "text": "/start",
        "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
    },
}

_BLOCKED_UPDATE = {
    "update_id": 2,
    "message": {
        "message_id": 2,
        "date": 1700000000,
        "chat": {"id": _BLOCKED_ID, "type": "private"},
        "from": {"id": _BLOCKED_ID, "is_bot": False, "first_name": "Stranger"},
        "text": "/start",
        "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
    },
}


@pytest.mark.asyncio
async def test_missing_secret_header_returns_403(test_app):
    resp = await test_app.post("/telegram/webhook", json=_START_UPDATE)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_wrong_secret_returns_403(test_app):
    resp = await test_app.post(
        "/telegram/webhook",
        json=_START_UPDATE,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_whitelisted_user_returns_403(test_app):
    resp = await test_app.post(
        "/telegram/webhook",
        json=_BLOCKED_UPDATE,
        headers={"X-Telegram-Bot-Api-Secret-Token": _SECRET},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_whitelisted_user_with_valid_secret_returns_200(test_app):
    resp = await test_app.post(
        "/telegram/webhook",
        json=_START_UPDATE,
        headers={"X-Telegram-Bot-Api-Secret-Token": _SECRET},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_healthz_is_unauthenticated(test_app):
    resp = await test_app.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
