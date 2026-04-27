"""Domain models for extracted Hebrew ticket data + draft state.

Fields are deliberately ``str | None`` so Hebrew text is preserved verbatim
from Gemini (no coercion to datetime/Decimal); Phase 04 re-parses when
building the wallet pass. ``raw_text`` holds Gemini's full transcription for
debugging only — it MUST NOT appear in INFO-level logs.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


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
