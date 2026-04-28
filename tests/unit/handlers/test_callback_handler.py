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
        "wallet" in text.lower() or "got it" in text.lower() for _cid, text in fake_client.sent
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


# ── wallet bundle flow ────────────────────────────────────────────────────────

from wallet_bot.models.callback_ids import CallbackId  # noqa: E402
from wallet_bot.models.wallet import WalletObject  # noqa: E402
from wallet_bot.services.pass_store import PassStore  # noqa: E402


def _approved_ticket(
    event: str = "Rock Concert",
    date: str = "2026-06-01",
    barcode: str | None = "BC001",
) -> ExtractedTicket:
    return ExtractedTicket(
        event_name=event,
        date=date,
        barcode=BarcodeResult(barcode_type="QR_CODE", barcode_value=barcode) if barcode else None,
    )


class FakeWalletService:
    def __init__(self) -> None:
        self._counter = 0

    def build_object(self, chat_id: int, ticket: ExtractedTicket) -> WalletObject:
        self._counter += 1
        return WalletObject(
            object_dict={
                "id": f"123.{chat_id}_{self._counter}",
                "classId": "123.evt",
                "state": "ACTIVE",
            },
            class_id="123.evt",
            barcode_value=ticket.barcode.barcode_value if ticket.barcode else None,
        )

    def build_save_url(self, objects: list[WalletObject]) -> str:
        return f"https://pay.google.com/gp/v/save/fake_jwt_{len(objects)}"


@pytest.fixture
async def store() -> DraftStore:
    return DraftStore()


@pytest.fixture
def pass_store() -> PassStore:
    return PassStore()


@pytest.fixture
def wallet_svc() -> FakeWalletService:
    return FakeWalletService()


async def _approve(chat_id, client, draft_store, ps, wsvc, ticket):
    await draft_store.put(
        chat_id,
        DraftState(
            ticket=ticket,
            message_id=1,
            created_at=datetime.now(tz=UTC),
        ),
    )
    await handle_callback(
        chat_id=chat_id,
        client=client,
        callback_query_id="q1",
        callback_data=CallbackId.APPROVE,
        store=draft_store,
        pass_store=ps,
        wallet_service=wsvc,
    )


async def test_approve_creates_bundle_and_sends_get_link_button(
    fake_client, store, pass_store, wallet_svc
) -> None:
    await _approve(42, fake_client, store, pass_store, wallet_svc, _approved_ticket())
    bundle = await pass_store.get(42)
    assert bundle is not None
    assert len(bundle.objects) == 1
    assert len(fake_client.sent_with_keyboard) == 1
    rows = fake_client.sent_with_keyboard[0][2]
    assert rows[0][0].callback_data == CallbackId.WALLET_GET_LINK


async def test_approve_exact_match_adds_to_bundle(
    fake_client, store, pass_store, wallet_svc
) -> None:
    ticket1 = _approved_ticket(barcode="BC001")
    ticket2 = _approved_ticket(barcode="BC002")
    await _approve(42, fake_client, store, pass_store, wallet_svc, ticket1)
    fake_client.sent_with_keyboard.clear()
    await _approve(42, fake_client, store, pass_store, wallet_svc, ticket2)
    bundle = await pass_store.get(42)
    assert bundle is not None
    assert len(bundle.objects) == 2
    assert "2 tickets" in fake_client.sent_with_keyboard[0][1]


async def test_approve_duplicate_barcode_ignored(
    fake_client, store, pass_store, wallet_svc
) -> None:
    ticket = _approved_ticket(barcode="BC001")
    await _approve(42, fake_client, store, pass_store, wallet_svc, ticket)
    fake_client.sent.clear()
    await _approve(42, fake_client, store, pass_store, wallet_svc, ticket)
    bundle = await pass_store.get(42)
    assert bundle is not None
    assert len(bundle.objects) == 1
    assert any("already" in t.lower() for _, t in fake_client.sent)


async def test_approve_close_match_asks_user(fake_client, store, pass_store, wallet_svc) -> None:
    ticket1 = _approved_ticket(event="Rock Concert", date="2026-06-01")
    ticket2 = _approved_ticket(event="Rock Concert Festival", date="2026-06-01", barcode="BC002")
    await _approve(42, fake_client, store, pass_store, wallet_svc, ticket1)
    fake_client.sent_with_keyboard.clear()
    await _approve(42, fake_client, store, pass_store, wallet_svc, ticket2)
    bundle = await pass_store.get(42)
    assert bundle is not None
    assert len(bundle.objects) == 1
    assert bundle.pending_object is not None
    rows = fake_client.sent_with_keyboard[0][2]
    cb_ids = {btn.callback_data for row in rows for btn in row}
    assert CallbackId.WALLET_BUNDLE_YES in cb_ids
    assert CallbackId.WALLET_BUNDLE_NO in cb_ids


async def test_approve_no_match_ignores_ticket(fake_client, store, pass_store, wallet_svc) -> None:
    ticket1 = _approved_ticket(event="Rock Concert", date="2026-06-01")
    ticket2 = _approved_ticket(event="Jazz Night", date="2026-07-15", barcode="BC002")
    await _approve(42, fake_client, store, pass_store, wallet_svc, ticket1)
    fake_client.sent.clear()
    await _approve(42, fake_client, store, pass_store, wallet_svc, ticket2)
    bundle = await pass_store.get(42)
    assert bundle is not None
    assert len(bundle.objects) == 1
    assert any("ignored" in t.lower() for _, t in fake_client.sent)


async def test_wallet_get_link_sends_url_button_and_clears_bundle(
    fake_client, store, pass_store, wallet_svc
) -> None:
    await _approve(42, fake_client, store, pass_store, wallet_svc, _approved_ticket())
    fake_client.sent_url_buttons.clear()
    await handle_callback(
        chat_id=42,
        client=fake_client,
        callback_query_id="q2",
        callback_data=CallbackId.WALLET_GET_LINK,
        store=store,
        pass_store=pass_store,
        wallet_service=wallet_svc,
    )
    assert len(fake_client.sent_url_buttons) == 1
    _, _, btn_text, url = fake_client.sent_url_buttons[0]
    assert "wallet" in btn_text.lower()
    assert url.startswith("https://pay.google.com/gp/v/save/")
    assert await pass_store.get(42) is None


async def test_wallet_bundle_yes_confirms_pending(
    fake_client, store, pass_store, wallet_svc
) -> None:
    ticket1 = _approved_ticket(event="Rock Concert", date="2026-06-01")
    ticket2 = _approved_ticket(event="Rock Concert Festival", date="2026-06-01", barcode="BC002")
    await _approve(42, fake_client, store, pass_store, wallet_svc, ticket1)
    await _approve(42, fake_client, store, pass_store, wallet_svc, ticket2)
    assert (await pass_store.get(42)).pending_object is not None

    fake_client.sent_with_keyboard.clear()
    await handle_callback(
        chat_id=42,
        client=fake_client,
        callback_query_id="q3",
        callback_data=CallbackId.WALLET_BUNDLE_YES,
        store=store,
        pass_store=pass_store,
        wallet_service=wallet_svc,
    )
    bundle = await pass_store.get(42)
    assert bundle is not None
    assert len(bundle.objects) == 2
    assert bundle.pending_object is None


async def test_wallet_bundle_no_discards_pending(
    fake_client, store, pass_store, wallet_svc
) -> None:
    ticket1 = _approved_ticket(event="Rock Concert", date="2026-06-01")
    ticket2 = _approved_ticket(event="Rock Concert Festival", date="2026-06-01", barcode="BC002")
    await _approve(42, fake_client, store, pass_store, wallet_svc, ticket1)
    await _approve(42, fake_client, store, pass_store, wallet_svc, ticket2)

    await handle_callback(
        chat_id=42,
        client=fake_client,
        callback_query_id="q4",
        callback_data=CallbackId.WALLET_BUNDLE_NO,
        store=store,
        pass_store=pass_store,
        wallet_service=wallet_svc,
    )
    bundle = await pass_store.get(42)
    assert bundle is not None
    assert len(bundle.objects) == 1
    assert bundle.pending_object is None
    assert any("ignored" in t.lower() for _, t in fake_client.sent)
