"""Domain models for extracted Hebrew ticket data + draft state.

Fields are deliberately ``str | None`` so Hebrew text is preserved verbatim
from Gemini (no coercion to datetime/Decimal); Phase 04 re-parses when
building the wallet pass. ``raw_text`` holds Gemini's full transcription for
debugging only — it MUST NOT appear in INFO-level logs. ``barcode_value``
holds the decoded barcode payload — also excluded from INFO logs (may be a
signed token).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class BarcodeResult(BaseModel):
    """Barcode or QR payload decoded from the ticket image by Gemini Vision."""

    barcode_type: str
    barcode_value: str | None = None

    @field_validator("barcode_value")
    @classmethod
    def _empty_to_none(cls, v: str | None) -> str | None:
        return None if v == "" else v


class ExtractedTicket(BaseModel):
    """Structured ticket fields extracted by the vision service."""

    event_name: str | None = None
    venue: str | None = None
    venue_address: str | None = None
    date: str | None = None
    time: str | None = None
    section: str | None = None
    holder_name: str | None = None
    order_number: str | None = None
    ticket_id: str | None = None
    price: str | None = None
    barcode: BarcodeResult | None = None
    raw_text: str = Field(
        default="",
        description="Full Gemini transcription — DEBUG ONLY. Exclude from INFO logs.",
    )


class DraftState(BaseModel):
    """In-memory per-chat draft being edited before approval."""

    ticket: ExtractedTicket
    editing_field: str | None = None
    message_id: int
    created_at: datetime
