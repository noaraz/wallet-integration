"""Tests for handle_edit_reply — user types a new value for the editing field."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from wallet_bot.handlers.edit_reply_handler import handle_edit_reply
from wallet_bot.models.ticket import DraftState, ExtractedTicket
from wallet_bot.services.draft_store import DraftStore


def _draft_editing(field: str) -> DraftState:
    return DraftState(
        ticket=ExtractedTicket(event_name="old", venue="old-venue"),
        editing_field=field,
        message_id=99,
        created_at=datetime.now(tz=UTC),
    )


@pytest.fixture
async def store() -> DraftStore:
    return DraftStore()


async def test_edit_sends_confirmation_reply(fake_client, store) -> None:
    """User scrolls down to type the new value — they need a visible
    'got it' next to where they're looking, not a silent in-place edit
    far above. The confirmation must include the human label of the field
    so the user knows what changed."""
    await store.put(42, _draft_editing("venue_address"))

    await handle_edit_reply(
        chat_id=42,
        client=fake_client,
        text="גני יהושע",
        store=store,
    )

    confirmations = [text for cid, text in fake_client.sent if cid == 42]
    assert confirmations, "expected a confirmation reply"
    # Confirmation references the human label, not the snake_case attr.
    msg = confirmations[-1].lower()
    assert "address" in msg
    assert "venue_address" not in msg  # raw attr name must not leak


async def test_typing_indicator_is_sent_during_edit(fake_client, store) -> None:
    """Even though the edit path is fast, the user needs an instant ack."""
    await store.put(42, _draft_editing("event_name"))

    await handle_edit_reply(
        chat_id=42,
        client=fake_client,
        text="גיא מזיג",
        store=store,
    )

    assert (42, "typing") in fake_client.chat_actions


async def test_applies_edit_and_rerenders_draft(fake_client, store) -> None:
    await store.put(42, _draft_editing("event_name"))

    await handle_edit_reply(
        chat_id=42,
        client=fake_client,
        text="גיא מזיג",
        store=store,
    )

    draft = await store.get(42)
    assert draft is not None
    assert draft.ticket.event_name == "גיא מזיג"
    assert draft.editing_field is None

    # Original draft message was edited in place with the new values.
    assert len(fake_client.edited) == 1
    chat_id, message_id, text, rows = fake_client.edited[0]
    assert chat_id == 42
    assert message_id == 99
    assert "גיא מזיג" in text
    assert rows


async def test_reply_when_not_editing_is_ignored(fake_client, store) -> None:
    draft = _draft_editing(field=None)  # type: ignore[arg-type]
    draft = draft.model_copy(update={"editing_field": None})
    await store.put(42, draft)

    await handle_edit_reply(chat_id=42, client=fake_client, text="ignored", store=store)

    # Nothing edited, nothing stored as new value.
    assert fake_client.edited == []
    d = await store.get(42)
    assert d is not None
    assert d.ticket.event_name == "old"


async def test_reply_without_draft_is_ignored(fake_client, store) -> None:
    await handle_edit_reply(chat_id=99, client=fake_client, text="anything", store=store)
    assert fake_client.edited == []


async def test_empty_text_is_ignored(fake_client, store) -> None:
    await store.put(42, _draft_editing("event_name"))
    await handle_edit_reply(chat_id=42, client=fake_client, text="", store=store)
    # Empty edits don't overwrite. Draft still editing.
    d = await store.get(42)
    assert d is not None
    assert d.ticket.event_name == "old"
    assert d.editing_field == "event_name"
