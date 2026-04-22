"""Render an ExtractedTicket as a Telegram message + inline keyboard.

Kept separate from the handlers so photo/callback/edit flows all produce
the same layout — one source of truth for labels and button order. The
output is plain text (no Markdown/HTML) and ``raw_text`` is never shown.
"""

from __future__ import annotations

from wallet_bot.models.callback_ids import CallbackId
from wallet_bot.models.ticket import ExtractedTicket
from wallet_bot.services.telegram_client import InlineButton

EM_DASH = "—"


# (ticket attribute, human label, callback) — order = display order.
_FIELDS: list[tuple[str, str, CallbackId]] = [
    ("event_name", "Event", CallbackId.EDIT_EVENT_NAME),
    ("venue", "Venue", CallbackId.EDIT_VENUE),
    ("venue_address", "Address", CallbackId.EDIT_VENUE_ADDRESS),
    ("date", "Date", CallbackId.EDIT_DATE),
    ("time", "Time", CallbackId.EDIT_TIME),
    ("section", "Section", CallbackId.EDIT_SECTION),
    ("holder_name", "Holder", CallbackId.EDIT_HOLDER_NAME),
    ("order_number", "Order #", CallbackId.EDIT_ORDER_NUMBER),
    ("ticket_id", "Ticket ID", CallbackId.EDIT_TICKET_ID),
    ("price", "Price", CallbackId.EDIT_PRICE),
]


def render_draft(ticket: ExtractedTicket) -> tuple[str, list[list[InlineButton]]]:
    """Return ``(message_text, keyboard_rows)`` for a ticket draft."""
    lines = ["Please review the ticket. Tap a field to edit."]
    for attr, label, _cb in _FIELDS:
        value = getattr(ticket, attr) or EM_DASH
        lines.append(f"{label}: {value}")
    text = "\n".join(lines)

    rows: list[list[InlineButton]] = [
        [InlineButton(text=f"✏️ {label}", callback_data=cb.value)] for _attr, label, cb in _FIELDS
    ]
    rows.append(
        [
            InlineButton(text="✅ Approve", callback_data=CallbackId.APPROVE.value),
            InlineButton(text="❌ Cancel", callback_data=CallbackId.CANCEL.value),
        ]
    )
    return text, rows


def field_prompt(label: str) -> str:
    """Prompt text for the ForceReply when the user taps an edit button."""
    return f"Send the corrected {label}"


def label_for(callback: CallbackId) -> str | None:
    for _attr, label, cb in _FIELDS:
        if cb is callback:
            return label
    return None
