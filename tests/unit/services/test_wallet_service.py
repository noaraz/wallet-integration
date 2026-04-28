"""Tests for WalletService."""

from __future__ import annotations

import json

import pytest

from wallet_bot.models.ticket import BarcodeResult, ExtractedTicket
from wallet_bot.models.wallet import WalletObject

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_sa_json() -> str:
    """Generate a minimal fake service-account JSON with a real RSA key."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return json.dumps(
        {
            "type": "service_account",
            "project_id": "test",
            "private_key_id": "k1",
            "private_key": pem,
            "client_email": "bot@test.iam.gserviceaccount.com",
            "client_id": "1",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    )


ISSUER_ID = "3388000000012345678"


@pytest.fixture
def svc():
    from wallet_bot.services.wallet_service import WalletService

    return WalletService(
        issuer_id=ISSUER_ID,
        sa_json=_make_sa_json(),
        origins=["https://example.com"],
    )


# ── build_object tests ────────────────────────────────────────────────────────


def test_build_object_returns_wallet_object(svc) -> None:
    ticket = ExtractedTicket(event_name="Rock Fest", date="2026-06-01")
    obj = svc.build_object(chat_id=42, ticket=ticket)
    assert isinstance(obj, WalletObject)


def test_build_object_id_starts_with_issuer(svc) -> None:
    ticket = ExtractedTicket(event_name="Rock Fest", date="2026-06-01")
    obj = svc.build_object(chat_id=42, ticket=ticket)
    assert obj.object_dict["id"].startswith(ISSUER_ID + ".")


def test_build_object_class_id_is_deterministic(svc) -> None:
    ticket = ExtractedTicket(event_name="Rock Fest", date="2026-06-01")
    obj1 = svc.build_object(chat_id=42, ticket=ticket)
    obj2 = svc.build_object(chat_id=42, ticket=ticket)
    assert obj1.class_id == obj2.class_id
    assert obj1.object_dict["classId"] == obj2.object_dict["classId"]


def test_build_object_includes_barcode_when_present(svc) -> None:
    ticket = ExtractedTicket(
        event_name="Rock Fest",
        date="2026-06-01",
        barcode=BarcodeResult(barcode_type="QR_CODE", barcode_value="TICKET123"),
    )
    obj = svc.build_object(chat_id=42, ticket=ticket)
    assert "barcode" in obj.object_dict
    assert obj.object_dict["barcode"]["value"] == "TICKET123"
    assert obj.barcode_value == "TICKET123"


def test_build_object_omits_barcode_when_value_is_none(svc) -> None:
    ticket = ExtractedTicket(
        event_name="Rock Fest",
        date="2026-06-01",
        barcode=BarcodeResult(barcode_type="QR_CODE", barcode_value=None),
    )
    obj = svc.build_object(chat_id=42, ticket=ticket)
    assert "barcode" not in obj.object_dict
    assert obj.barcode_value is None


def test_build_object_omits_barcode_when_no_barcode_field(svc) -> None:
    ticket = ExtractedTicket(event_name="Concert", date="2026-06-01")
    obj = svc.build_object(chat_id=42, ticket=ticket)
    assert "barcode" not in obj.object_dict


def test_build_object_state_is_active(svc) -> None:
    ticket = ExtractedTicket(event_name="Concert", date="2026-06-01")
    obj = svc.build_object(chat_id=42, ticket=ticket)
    assert obj.object_dict["state"] == "ACTIVE"


def test_build_object_object_id_stable_with_barcode(svc) -> None:
    """Same barcode → same object ID (deterministic, enables dedup at Wallet API)."""
    ticket = ExtractedTicket(
        event_name="Concert",
        date="2026-06-01",
        barcode=BarcodeResult(barcode_type="QR_CODE", barcode_value="BC-999"),
    )
    id1 = svc.build_object(chat_id=42, ticket=ticket).object_dict["id"]
    id2 = svc.build_object(chat_id=42, ticket=ticket).object_dict["id"]
    assert id1 == id2


def test_build_object_different_chat_ids_differ(svc) -> None:
    ticket = ExtractedTicket(
        event_name="Concert",
        date="2026-06-01",
        barcode=BarcodeResult(barcode_type="QR_CODE", barcode_value="BC-999"),
    )
    id1 = svc.build_object(chat_id=42, ticket=ticket).object_dict["id"]
    id2 = svc.build_object(chat_id=99, ticket=ticket).object_dict["id"]
    assert id1 != id2


# ── build_save_url tests ─────────────────────────────────────────────────────


def test_build_save_url_format(svc) -> None:
    ticket = ExtractedTicket(event_name="Concert", date="2026-06-01")
    obj = svc.build_object(chat_id=42, ticket=ticket)
    url = svc.build_save_url([obj])
    assert url.startswith("https://pay.google.com/gp/v/save/")


def test_build_save_url_jwt_has_three_parts(svc) -> None:
    ticket = ExtractedTicket(event_name="Concert", date="2026-06-01")
    obj = svc.build_object(chat_id=42, ticket=ticket)
    url = svc.build_save_url([obj])
    jwt_part = url.removeprefix("https://pay.google.com/gp/v/save/")
    assert jwt_part.count(".") == 2


def test_build_save_url_payload_claims(svc) -> None:
    import base64

    ticket = ExtractedTicket(event_name="Concert", date="2026-06-01")
    obj = svc.build_object(chat_id=42, ticket=ticket)
    url = svc.build_save_url([obj])
    jwt_part = url.removeprefix("https://pay.google.com/gp/v/save/")
    _, payload_b64, _ = jwt_part.split(".")
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    assert payload["aud"] == "google"
    assert payload["typ"] == "savetowallet"
    assert payload["iss"] == "bot@test.iam.gserviceaccount.com"
    assert "iat" in payload
    assert "payload" in payload
    assert "eventTicketObjects" in payload["payload"]
    assert len(payload["payload"]["eventTicketObjects"]) == 1


def test_build_save_url_multiple_objects(svc) -> None:
    import base64

    ticket1 = ExtractedTicket(
        event_name="Concert",
        date="2026-06-01",
        barcode=BarcodeResult(barcode_type="QR_CODE", barcode_value="BC1"),
    )
    ticket2 = ExtractedTicket(
        event_name="Concert",
        date="2026-06-01",
        barcode=BarcodeResult(barcode_type="QR_CODE", barcode_value="BC2"),
    )
    objects = [
        svc.build_object(chat_id=42, ticket=ticket1),
        svc.build_object(chat_id=42, ticket=ticket2),
    ]
    url = svc.build_save_url(objects)
    jwt_part = url.removeprefix("https://pay.google.com/gp/v/save/")
    _, payload_b64, _ = jwt_part.split(".")
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    assert len(payload["payload"]["eventTicketObjects"]) == 2
