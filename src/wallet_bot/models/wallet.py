"""Domain models for Google Wallet pass building."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class WalletObject(BaseModel):
    """A built eventTicketObject dict plus metadata for dedup."""

    object_dict: dict  # type: ignore[type-arg]
    class_id: str
    barcode_value: str | None = None


class PassBundle(BaseModel):
    """Active per-chat bundle accumulating objects for one event."""

    event_name: str
    date: str
    class_id: str
    objects: list[WalletObject] = Field(default_factory=list)
    pending_object: WalletObject | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    def has_barcode(self, barcode_value: str) -> bool:
        """Return True if any confirmed object in the bundle carries this barcode."""
        return any(
            obj.barcode_value == barcode_value
            for obj in self.objects
            if obj.barcode_value is not None
        )
