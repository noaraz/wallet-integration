"""Tests for wallet domain models."""

from __future__ import annotations

from wallet_bot.models.wallet import PassBundle, WalletObject


def test_wallet_object_stores_dict_and_barcode() -> None:
    obj = WalletObject(
        object_dict={"id": "123.abc", "classId": "123.evt", "state": "ACTIVE"},
        class_id="123.evt",
        barcode_value="TICKET-001",
    )
    assert obj.object_dict["id"] == "123.abc"
    assert obj.barcode_value == "TICKET-001"


def test_wallet_object_barcode_value_optional() -> None:
    obj = WalletObject(
        object_dict={"id": "123.abc", "classId": "123.evt", "state": "ACTIVE"},
        class_id="123.evt",
    )
    assert obj.barcode_value is None


def test_pass_bundle_starts_empty() -> None:
    from datetime import UTC, datetime

    bundle = PassBundle(
        event_name="Rock Concert",
        date="2026-05-01",
        class_id="123.evt",
        created_at=datetime.now(tz=UTC),
    )
    assert bundle.objects == []
    assert bundle.pending_object is None


def test_pass_bundle_has_barcode_true() -> None:
    from datetime import UTC, datetime

    obj = WalletObject(object_dict={}, class_id="123.evt", barcode_value="BARCODE-XYZ")
    bundle = PassBundle(
        event_name="Concert",
        date="2026-05-01",
        class_id="123.evt",
        objects=[obj],
        created_at=datetime.now(tz=UTC),
    )
    assert bundle.has_barcode("BARCODE-XYZ") is True
    assert bundle.has_barcode("OTHER") is False


def test_pass_bundle_has_barcode_ignores_none_values() -> None:
    from datetime import UTC, datetime

    obj = WalletObject(object_dict={}, class_id="123.evt", barcode_value=None)
    bundle = PassBundle(
        event_name="Concert",
        date="2026-05-01",
        class_id="123.evt",
        objects=[obj],
        created_at=datetime.now(tz=UTC),
    )
    assert bundle.has_barcode("anything") is False
