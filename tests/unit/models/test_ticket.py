"""Tests for ExtractedTicket and DraftState domain models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from wallet_bot.models.ticket import DraftState, ExtractedTicket


class TestExtractedTicket:
    def test_all_fields_default_to_none(self) -> None:
        t = ExtractedTicket()
        assert t.event_name is None
        assert t.venue is None
        assert t.venue_address is None
        assert t.date is None
        assert t.time is None
        assert t.section is None
        assert t.holder_name is None
        assert t.order_number is None
        assert t.ticket_id is None
        assert t.price is None

    def test_raw_text_defaults_to_empty_string(self) -> None:
        assert ExtractedTicket().raw_text == ""

    def test_preserves_hebrew_verbatim(self) -> None:
        t = ExtractedTicket(event_name="גיא מזיג", venue="אמפי תל אביב", holder_name="נועה רז")
        assert t.event_name == "גיא מזיג"
        assert t.venue == "אמפי תל אביב"
        assert t.holder_name == "נועה רז"

    def test_model_dump_can_exclude_raw_text(self) -> None:
        t = ExtractedTicket(event_name="גיא מזיג", raw_text="full secret dump")
        dumped = t.model_dump(exclude={"raw_text"})
        assert "raw_text" not in dumped
        assert "full secret dump" not in str(dumped)
        assert dumped["event_name"] == "גיא מזיג"


class TestDraftState:
    def test_requires_ticket_and_message_id_and_created_at(self) -> None:
        with pytest.raises(ValidationError):
            DraftState()  # type: ignore[call-arg]

    def test_defaults_editing_field_to_none(self) -> None:
        state = DraftState(
            ticket=ExtractedTicket(),
            message_id=42,
            created_at=datetime.now(tz=UTC),
        )
        assert state.editing_field is None

    def test_round_trip_fields(self) -> None:
        now = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)
        state = DraftState(
            ticket=ExtractedTicket(event_name="גיא מזיג"),
            editing_field="event_name",
            message_id=7,
            created_at=now,
        )
        assert state.ticket.event_name == "גיא מזיג"
        assert state.editing_field == "event_name"
        assert state.message_id == 7
        assert state.created_at == now
