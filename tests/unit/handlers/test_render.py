"""Tests for the draft rendering helper."""

from __future__ import annotations

from wallet_bot.handlers._render import EM_DASH, render_draft
from wallet_bot.models.callback_ids import EDIT_FIELD_TO_TICKET_ATTR, CallbackId
from wallet_bot.models.ticket import ExtractedTicket


def test_render_draft_shows_all_fields() -> None:
    ticket = ExtractedTicket(
        event_name="גיא מזיג",
        venue="אמפי תל אביב",
        date="6.6",
        time="21:00",
        price="₪134",
    )
    text, _rows = render_draft(ticket)

    assert "גיא מזיג" in text
    assert "אמפי תל אביב" in text
    assert "21:00" in text
    assert "₪134" in text


def test_missing_fields_shown_as_em_dash() -> None:
    ticket = ExtractedTicket(event_name="גיא מזיג")
    text, _rows = render_draft(ticket)
    assert EM_DASH in text


def test_render_draft_never_includes_raw_text() -> None:
    ticket = ExtractedTicket(event_name="x", raw_text="watermark bleed bleed bleed")
    text, _rows = render_draft(ticket)
    assert "watermark bleed" not in text


def test_keyboard_has_one_edit_button_per_ticket_field_plus_approve_cancel() -> None:
    _text, rows = render_draft(ExtractedTicket())

    # Flatten callback_data values across all rows.
    callback_data = [btn.callback_data for row in rows for btn in row]

    # Every EDIT_* enum value appears exactly once.
    for cb in EDIT_FIELD_TO_TICKET_ATTR:
        assert cb.value in callback_data, cb

    assert CallbackId.APPROVE.value in callback_data
    assert CallbackId.CANCEL.value in callback_data


def test_keyboard_last_row_is_approve_cancel() -> None:
    _text, rows = render_draft(ExtractedTicket())
    last = [btn.callback_data for btn in rows[-1]]
    assert last == [CallbackId.APPROVE.value, CallbackId.CANCEL.value]
