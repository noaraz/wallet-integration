"""Whitelist of allowed Telegram callback_data values.

Security: every callback_query update is parsed through :func:`parse_callback_id`,
which returns ``None`` for anything outside the enum. No ``setattr`` or string
interpolation is ever driven by raw callback_data — the handler routes on the
enum member. ``raw_text`` is deliberately NOT represented here (debug-only).
"""

from __future__ import annotations

from enum import StrEnum


class CallbackId(StrEnum):
    EDIT_EVENT_NAME = "edit_event_name"
    EDIT_VENUE = "edit_venue"
    EDIT_VENUE_ADDRESS = "edit_venue_address"
    EDIT_DATE = "edit_date"
    EDIT_TIME = "edit_time"
    EDIT_SECTION = "edit_section"
    EDIT_HOLDER_NAME = "edit_holder_name"
    EDIT_ORDER_NUMBER = "edit_order_number"
    EDIT_TICKET_ID = "edit_ticket_id"
    EDIT_PRICE = "edit_price"
    APPROVE = "approve"
    CANCEL = "cancel"


# Map each EDIT_* callback to the matching ExtractedTicket attribute.
# Kept explicit (not auto-derived) so new ticket fields don't accidentally
# become user-editable without a conscious code change.
EDIT_FIELD_TO_TICKET_ATTR: dict[CallbackId, str] = {
    CallbackId.EDIT_EVENT_NAME: "event_name",
    CallbackId.EDIT_VENUE: "venue",
    CallbackId.EDIT_VENUE_ADDRESS: "venue_address",
    CallbackId.EDIT_DATE: "date",
    CallbackId.EDIT_TIME: "time",
    CallbackId.EDIT_SECTION: "section",
    CallbackId.EDIT_HOLDER_NAME: "holder_name",
    CallbackId.EDIT_ORDER_NUMBER: "order_number",
    CallbackId.EDIT_TICKET_ID: "ticket_id",
    CallbackId.EDIT_PRICE: "price",
}


def parse_callback_id(raw: object) -> CallbackId | None:
    """Return the enum member for ``raw`` or ``None`` if it is not whitelisted.

    Strict: exact string match, no stripping, no case-folding. Anything that
    isn't a ``str`` in the enum returns ``None``.
    """
    if not isinstance(raw, str):
        return None
    try:
        return CallbackId(raw)
    except ValueError:
        return None
