"""Tests for handle_callback — edit/approve/cancel button taps."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import pytest

from wallet_bot.handlers._safe import GENERIC_ERROR_REPLY
from wallet_bot.handlers.callback_handler import handle_callback
from wallet_bot.models.ticket import BarcodeResult, DraftState, ExtractedTicket
from wallet_bot.services.draft_store import DraftStore


def _draft(chat_id: int = 42, message_id: int = 99) -> DraftState:
    return DraftState(
        ticket=ExtractedTicket(
            event_name="גיא מזיג",
            venue="אמפי תל אביב",
            raw_text="FULL SECRET DEBUG DUMP — should never log",
        ),
        message_id=message_id,
        created_at=datetime.now(tz=UTC),
    )


@pytest.fixture
async def store_with_draft() -> DraftStore:
    s = DraftStore()
    await s.put(42, _draft())
    return s


async def test_unknown_callback_data_is_dropped(fake_client, store_with_draft) -> None:
    await handle_callback(
        chat_id=42,
        client=fake_client,
        callback_query_id="cb1",
        callback_data="edit_../../secret",
        store=store_with_draft,
    )

    # Telegram query acknowledged (so the spinner stops).
    assert fake_client.answered == ["cb1"]
    # No edits, no force-reply, no outbound text — request dropped silently.
    assert fake_client.edited == []
    assert fake_client.force_replies == []

    # Draft untouched.
    draft = await store_with_draft.get(42)
    assert draft is not None
    assert draft.editing_field is None


async def test_edit_button_sends_force_reply_and_marks_editing_field(
    fake_client, store_with_draft
) -> None:
    await handle_callback(
        chat_id=42,
        client=fake_client,
        callback_query_id="cb1",
        callback_data="edit_event_name",
        store=store_with_draft,
    )

    assert fake_client.answered == ["cb1"]
    assert len(fake_client.force_replies) == 1
    prompt_chat_id, prompt_text = fake_client.force_replies[0]
    assert prompt_chat_id == 42
    assert "event" in prompt_text.lower()

    draft = await store_with_draft.get(42)
    assert draft is not None
    assert draft.editing_field == "event_name"


async def test_edit_button_does_not_redundantly_edit_draft_message(
    fake_client, store_with_draft
) -> None:
    """Re-rendering an unchanged draft makes Telegram throw BadRequest:
    'Message is not modified', which @safe_handler then surfaces as a
    generic error reply — making the bot look broken on every edit tap."""
    await handle_callback(
        chat_id=42,
        client=fake_client,
        callback_query_id="cb1",
        callback_data="edit_event_name",
        store=store_with_draft,
    )

    assert fake_client.edited == []  # no useless edit_message_text call


async def test_approve_logs_ticket_and_clears_draft(fake_client, store_with_draft, caplog) -> None:
    with caplog.at_level(logging.INFO):
        await handle_callback(
            chat_id=42,
            client=fake_client,
            callback_query_id="cb1",
            callback_data="approve",
            store=store_with_draft,
        )

    assert fake_client.answered == ["cb1"]

    # Confirmation reply to user.
    assert any(
        "phase 04" in text.lower() or "got it" in text.lower() for _cid, text in fake_client.sent
    )

    # Exactly one "ticket_approved" log line, carrying JSON without raw_text.
    approval_lines = [r for r in caplog.records if "ticket_approved" in r.getMessage()]
    assert len(approval_lines) == 1
    line_text = approval_lines[0].getMessage()
    assert "FULL SECRET DEBUG DUMP" not in line_text
    payload = json.loads(line_text.split("ticket_approved ", 1)[1])
    assert "raw_text" not in payload
    assert payload["event_name"] == "גיא מזיג"

    # Draft cleared.
    assert await store_with_draft.get(42) is None


async def test_cancel_clears_draft_and_replies(fake_client, store_with_draft) -> None:
    await handle_callback(
        chat_id=42,
        client=fake_client,
        callback_query_id="cb1",
        callback_data="cancel",
        store=store_with_draft,
    )

    assert fake_client.answered == ["cb1"]
    assert any("cancel" in text.lower() for _cid, text in fake_client.sent)
    assert await store_with_draft.get(42) is None


async def test_callback_with_no_draft_is_noop(fake_client) -> None:
    empty_store = DraftStore()

    await handle_callback(
        chat_id=42,
        client=fake_client,
        callback_query_id="cb1",
        callback_data="approve",
        store=empty_store,
    )

    # Still ack the query, but no work to do.
    assert fake_client.answered == ["cb1"]
    assert fake_client.sent_with_keyboard == []
    assert fake_client.edited == []


async def test_callback_exception_produces_generic_reply(fake_client) -> None:
    class ExplodingStore(DraftStore):
        async def get(self, chat_id: int):
            raise RuntimeError("db down")

    store = ExplodingStore()
    await handle_callback(
        chat_id=42,
        client=fake_client,
        callback_query_id="cb1",
        callback_data="approve",
        store=store,
    )
    assert (42, GENERIC_ERROR_REPLY) in fake_client.sent


async def test_approve_excludes_barcode_value_from_log(fake_client, caplog) -> None:
    store = DraftStore()
    draft = DraftState(
        ticket=ExtractedTicket(
            event_name="גיא מזיג",
            barcode=BarcodeResult(
                barcode_type="QR_CODE",
                barcode_value="super-secret-signed-token",
            ),
            raw_text="debug dump",
        ),
        message_id=99,
        created_at=datetime.now(tz=UTC),
    )
    await store.put(42, draft)

    with caplog.at_level(logging.INFO):
        await handle_callback(
            chat_id=42,
            client=fake_client,
            callback_query_id="cb1",
            callback_data="approve",
            store=store,
        )

    approval_lines = [r for r in caplog.records if "ticket_approved" in r.getMessage()]
    assert len(approval_lines) == 1
    line_text = approval_lines[0].getMessage()
    # Sensitive payload must be absent.
    assert "super-secret-signed-token" not in line_text
    assert "barcode_value" not in line_text
    # Safe metadata stays.
    payload = json.loads(line_text.split("ticket_approved ", 1)[1])
    assert payload["barcode"]["barcode_type"] == "QR_CODE"
