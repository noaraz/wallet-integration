"""Tests for the callback-id whitelist (security: reject unknown callback_data)."""

from __future__ import annotations

import pytest
from wallet_bot.models.callback_ids import (
    EDIT_FIELD_TO_TICKET_ATTR,
    CallbackId,
    parse_callback_id,
)

from wallet_bot.models.ticket import ExtractedTicket


class TestCallbackId:
    def test_all_edit_ids_map_to_real_ticket_fields(self) -> None:
        ticket_fields = set(ExtractedTicket.model_fields.keys())
        for cb_id, attr in EDIT_FIELD_TO_TICKET_ATTR.items():
            assert cb_id.value.startswith("edit_"), cb_id
            assert attr in ticket_fields, f"{cb_id} -> {attr} not a ticket field"

    def test_edit_map_excludes_raw_text(self) -> None:
        # raw_text is debug-only; must NOT be user-editable via callback.
        attrs = set(EDIT_FIELD_TO_TICKET_ATTR.values())
        assert "raw_text" not in attrs

    def test_approve_and_cancel_exist(self) -> None:
        assert CallbackId.APPROVE.value == "approve"
        assert CallbackId.CANCEL.value == "cancel"


class TestParseCallbackId:
    def test_valid_edit_id_round_trip(self) -> None:
        assert parse_callback_id("edit_event_name") is CallbackId.EDIT_EVENT_NAME
        assert parse_callback_id("approve") is CallbackId.APPROVE
        assert parse_callback_id("cancel") is CallbackId.CANCEL

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "edit_",
            "edit_raw_text",  # explicitly forbidden
            "edit_../../secret",
            "EDIT_EVENT_NAME",  # case-sensitive
            "approve\n",
            " approve",
            "edit_event_name; rm -rf /",
            "unknown",
        ],
    )
    def test_malformed_rejected(self, raw: str) -> None:
        assert parse_callback_id(raw) is None

    def test_non_string_rejected(self) -> None:
        assert parse_callback_id(None) is None  # type: ignore[arg-type]
        assert parse_callback_id(123) is None  # type: ignore[arg-type]
