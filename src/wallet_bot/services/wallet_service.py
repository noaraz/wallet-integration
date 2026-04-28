"""Google Wallet pass builder and JWT signer.

Local dev: pass ``sa_json`` (full service-account JSON string).
Prod (Phase 07+): migrate to ADC / IAM signing; ``sa_json`` can be None.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid

from google.auth import crypt
from google.auth import jwt as google_jwt

from wallet_bot.models.ticket import ExtractedTicket
from wallet_bot.models.wallet import WalletObject

_BARCODE_TYPE_MAP: dict[str, str] = {
    "QR_CODE": "QR_CODE",
    "QR": "QR_CODE",
    "CODE_128": "CODE_128",
    "BARCODE_128": "CODE_128",
    "CODE128": "CODE_128",
    "AZTEC": "AZTEC",
    "PDF_417": "PDF_417",
    "PDF417": "PDF_417",
}
_DEFAULT_BARCODE_TYPE = "QR_CODE"


def _stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def _map_barcode_type(raw: str) -> str:
    return _BARCODE_TYPE_MAP.get(raw.upper(), _DEFAULT_BARCODE_TYPE)


class WalletService:
    def __init__(
        self,
        issuer_id: str,
        sa_json: str,
        origins: list[str],
    ) -> None:
        info = json.loads(sa_json)
        self._signer = crypt.RSASigner.from_service_account_info(info)
        self._issuer_id = issuer_id
        self._issuer_email: str = info["client_email"]
        self._origins = origins

    def build_object(self, chat_id: int, ticket: ExtractedTicket) -> WalletObject:
        """Build an eventTicketObject dict from an approved ticket."""
        class_id = self._class_id(ticket)
        object_id = self._object_id(chat_id, ticket)

        obj: dict = {  # type: ignore[type-arg]
            "id": object_id,
            "classId": class_id,
            "state": "ACTIVE",
        }

        if ticket.event_name:
            obj["eventName"] = {"defaultValue": {"language": "iw", "value": ticket.event_name}}
        if ticket.holder_name:
            obj["ticketHolderName"] = ticket.holder_name
        if ticket.venue:
            obj["venue"] = {"name": {"defaultValue": {"language": "iw", "value": ticket.venue}}}
        if ticket.date or ticket.time:
            date_str = ticket.date or ""
            time_str = ticket.time or ""
            obj["dateTime"] = f"{date_str} {time_str}".strip()
        if ticket.section:
            obj["seatInfo"] = {
                "section": {"defaultValue": {"language": "iw", "value": ticket.section}}
            }

        # Barcode: omit entirely when value is absent — it is an optional field.
        if ticket.barcode and ticket.barcode.barcode_value:
            obj["barcode"] = {
                "type": _map_barcode_type(ticket.barcode.barcode_type),
                "value": ticket.barcode.barcode_value,
            }

        barcode_value = (
            ticket.barcode.barcode_value
            if ticket.barcode and ticket.barcode.barcode_value
            else None
        )
        return WalletObject(
            object_dict=obj,
            class_id=class_id,
            barcode_value=barcode_value,
        )

    def _class_id(self, ticket: ExtractedTicket) -> str:
        key = f"{ticket.event_name or ''}|{ticket.date or ''}"
        return f"{self._issuer_id}.event_{_stable_hash(key)}"

    def _object_id(self, chat_id: int, ticket: ExtractedTicket) -> str:
        raw = (ticket.barcode.barcode_value if ticket.barcode else None) or ticket.ticket_id
        suffix = _stable_hash(raw) if raw else uuid.uuid4().hex[:20]
        return f"{self._issuer_id}.{chat_id}_{suffix}"

    def build_save_url(self, objects: list[WalletObject]) -> str:
        """Sign a savetowallet JWT and return the Google Wallet save URL."""
        payload = {
            "iss": self._issuer_email,
            "aud": "google",
            "typ": "savetowallet",
            "iat": int(time.time()),
            "origins": self._origins,
            "payload": {
                "eventTicketObjects": [obj.object_dict for obj in objects],
            },
        }
        token: bytes = google_jwt.encode(self._signer, payload)
        return f"https://pay.google.com/gp/v/save/{token.decode()}"
