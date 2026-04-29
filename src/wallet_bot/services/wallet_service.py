"""Google Wallet pass builder and JWT signer.

Local dev: pass ``sa_json`` (full service-account JSON string).
Prod (Phase 07+): migrate to ADC / IAM signing; ``sa_json`` can be None.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.parse
import uuid

import httpx
from google.auth import crypt
from google.auth import jwt as google_jwt
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import service_account

from wallet_bot.models.ticket import ExtractedTicket
from wallet_bot.models.wallet import WalletObject

_logger = logging.getLogger(__name__)

_WALLET_API = "https://walletobjects.googleapis.com/walletobjects/v1"
_WALLET_SCOPES = ["https://www.googleapis.com/auth/wallet_object.issuer"]

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

# Deep indigo — distinctive concert-ticket colour, readable on white barcode.
_PASS_BACKGROUND_COLOR = "#1A237E"

_CLASS_TEMPLATE = {
    "cardTemplateOverride": {
        "cardRowTemplateInfos": [
            {
                "twoItems": {
                    "startItem": {
                        "firstValue": {
                            "fields": [{"fieldPath": "object.textModulesData['datetime']"}]
                        }
                    },
                    "endItem": {
                        "firstValue": {"fields": [{"fieldPath": "object.textModulesData['venue']"}]}
                    },
                }
            },
            {
                "twoItems": {
                    "startItem": {
                        "firstValue": {
                            "fields": [{"fieldPath": "object.textModulesData['venue_address']"}]
                        }
                    },
                    "endItem": {
                        "firstValue": {"fields": [{"fieldPath": "object.textModulesData['order']"}]}
                    },
                }
            },
            {
                "oneItem": {
                    "item": {
                        "firstValue": {
                            "fields": [{"fieldPath": "object.textModulesData['holder']"}]
                        }
                    }
                }
            },
        ]
    }
}


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
        self._creds = service_account.Credentials.from_service_account_info(
            info, scopes=_WALLET_SCOPES
        )
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

        text_modules = []
        if ticket.date or ticket.time:
            body = " ".join(filter(None, [ticket.date, ticket.time]))
            text_modules.append({"header": "תאריך ושעה", "body": body, "id": "datetime"})
        if ticket.venue:
            text_modules.append({"header": "מקום", "body": ticket.venue, "id": "venue"})
        if ticket.venue_address:
            text_modules.append(
                {"header": "כתובת", "body": ticket.venue_address, "id": "venue_address"}
            )
        if ticket.holder_name:
            text_modules.append({"header": "שם", "body": ticket.holder_name, "id": "holder"})
        if ticket.order_number:
            text_modules.append({"header": "הזמנה", "body": ticket.order_number, "id": "order"})
        if text_modules:
            obj["textModulesData"] = text_modules

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

    def _build_class_dict(self, class_id: str, event_name: str | None) -> dict:  # type: ignore[type-arg]
        d: dict = {  # type: ignore[type-arg]
            "id": class_id,
            "issuerName": "Wallet Bot",
            "reviewStatus": "UNDER_REVIEW",
            "hexBackgroundColor": _PASS_BACKGROUND_COLOR,
            "classTemplateInfo": _CLASS_TEMPLATE,
        }
        if event_name:
            d["eventName"] = {"defaultValue": {"language": "iw", "value": event_name}}
        return d

    def _auth_token(self) -> str:
        if not self._creds.valid:
            self._creds.refresh(GoogleRequest())
        return self._creds.token  # type: ignore[return-value]

    async def _upsert_class(self, class_dict: dict) -> None:  # type: ignore[type-arg]
        """Create or update the class so classTemplateInfo and colour always apply."""
        encoded_id = urllib.parse.quote(class_dict["id"], safe="")
        base_url = f"{_WALLET_API}/eventTicketClass"
        try:
            headers = {
                "Authorization": f"Bearer {self._auth_token()}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.patch(
                    f"{base_url}/{encoded_id}", json=class_dict, headers=headers
                )
                if resp.status_code == 404:
                    resp = await client.post(base_url, json=class_dict, headers=headers)
            if resp.status_code not in (200, 201):
                _logger.warning("class upsert %s: %s", resp.status_code, resp.text[:200])
        except Exception as exc:
            _logger.warning("class upsert failed (non-fatal): %s", exc)

    async def build_save_url(self, objects: list[WalletObject]) -> str:
        """Sign a savetowallet JWT and return the Google Wallet save URL."""
        seen_classes: dict[str, dict] = {}  # type: ignore[type-arg]
        for obj in objects:
            if obj.class_id not in seen_classes:
                event_name = (
                    obj.object_dict.get("eventName", {}).get("defaultValue", {}).get("value")
                )
                seen_classes[obj.class_id] = self._build_class_dict(obj.class_id, event_name)

        for class_dict in seen_classes.values():
            await self._upsert_class(class_dict)

        payload = {
            "iss": self._issuer_email,
            "aud": "google",
            "typ": "savetowallet",
            "iat": int(time.time()),
            "origins": self._origins,
            "payload": {
                "eventTicketClasses": list(seen_classes.values()),
                "eventTicketObjects": [obj.object_dict for obj in objects],
            },
        }
        token: bytes = google_jwt.encode(self._signer, payload)
        return f"https://pay.google.com/gp/v/save/{token.decode()}"
