"""Tests for ExtractedTicket and DraftState domain models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from wallet_bot.models.ticket import BarcodeResult, DraftState, ExtractedTicket


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


class TestBarcodeResult:
    def test_valid_barcode(self) -> None:
        b = BarcodeResult(barcode_type="QR_CODE", barcode_value="https://ticket.example/abc123")
        assert b.barcode_type == "QR_CODE"
        assert b.barcode_value == "https://ticket.example/abc123"

    def test_empty_value_normalised_to_none(self) -> None:
        b = BarcodeResult(barcode_type="QR_CODE", barcode_value="")
        assert b.barcode_value is None

    def test_none_value_stays_none(self) -> None:
        b = BarcodeResult(barcode_type="QR_CODE", barcode_value=None)
        assert b.barcode_value is None

    def test_barcode_type_is_required(self) -> None:
        with pytest.raises(ValidationError):
            BarcodeResult(barcode_value="something")  # type: ignore[call-arg]


class TestExtractedTicketBarcode:
    def test_barcode_defaults_to_none(self) -> None:
        assert ExtractedTicket().barcode is None

    def test_barcode_parses_nested_dict(self) -> None:
        t = ExtractedTicket(
            barcode={"barcode_type": "QR_CODE", "barcode_value": "https://x.example"}
        )
        assert t.barcode is not None
        assert t.barcode.barcode_type == "QR_CODE"
        assert t.barcode.barcode_value == "https://x.example"

    def test_barcode_parses_instance(self) -> None:
        b = BarcodeResult(barcode_type="CODE_128", barcode_value="ABC-123")
        t = ExtractedTicket(barcode=b)
        assert t.barcode is b

    def test_model_dump_can_exclude_barcode_value(self) -> None:
        t = ExtractedTicket(
            event_name="גיא מזיג",
            barcode=BarcodeResult(barcode_type="QR_CODE", barcode_value="secret-token"),
        )
        dumped = t.model_dump(exclude={"raw_text": True, "barcode": {"barcode_value"}})
        assert "secret-token" not in str(dumped)
        assert dumped["barcode"]["barcode_type"] == "QR_CODE"
        assert "barcode_value" not in dumped["barcode"]

    def test_existing_fields_unaffected_by_barcode_addition(self) -> None:
        t = ExtractedTicket(event_name="גיא מזיג", venue="אמפי תל אביב")
        assert t.barcode is None
        assert t.event_name == "גיא מזיג"
