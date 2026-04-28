"""Tests for PassStore."""

from __future__ import annotations

from wallet_bot.models.wallet import PassBundle, WalletObject
from wallet_bot.services.pass_store import PassStore


def _obj(barcode: str | None = "B1") -> WalletObject:
    return WalletObject(object_dict={"id": "x"}, class_id="c", barcode_value=barcode)


def _bundle(**kw) -> PassBundle:
    from datetime import UTC, datetime

    return PassBundle(
        event_name=kw.get("event_name", "Concert"),
        date=kw.get("date", "2026-05-01"),
        class_id=kw.get("class_id", "123.evt"),
        created_at=datetime.now(tz=UTC),
    )


async def test_get_returns_none_for_unknown_chat() -> None:
    store = PassStore()
    assert await store.get(999) is None


async def test_put_and_get_roundtrip() -> None:
    store = PassStore()
    bundle = _bundle()
    await store.put(42, bundle)
    result = await store.get(42)
    assert result is not None
    assert result.event_name == "Concert"


async def test_add_object_appends() -> None:
    store = PassStore()
    await store.put(42, _bundle())
    await store.add_object(42, _obj("B1"))
    await store.add_object(42, _obj("B2"))
    bundle = await store.get(42)
    assert bundle is not None
    assert len(bundle.objects) == 2


async def test_has_barcode_true_and_false() -> None:
    store = PassStore()
    await store.put(42, _bundle())
    await store.add_object(42, _obj("B1"))
    assert await store.has_barcode(42, "B1") is True
    assert await store.has_barcode(42, "OTHER") is False


async def test_has_barcode_false_when_no_bundle() -> None:
    store = PassStore()
    assert await store.has_barcode(99, "anything") is False


async def test_set_pending_and_confirm() -> None:
    store = PassStore()
    await store.put(42, _bundle())
    pending = _obj("P1")
    await store.set_pending(42, pending)
    bundle = await store.get(42)
    assert bundle is not None
    assert bundle.pending_object is not None
    assert bundle.pending_object.barcode_value == "P1"
    assert len(bundle.objects) == 0

    await store.confirm_pending(42)
    bundle = await store.get(42)
    assert bundle is not None
    assert bundle.pending_object is None
    assert len(bundle.objects) == 1
    assert bundle.objects[0].barcode_value == "P1"


async def test_discard_pending() -> None:
    store = PassStore()
    await store.put(42, _bundle())
    await store.set_pending(42, _obj("P1"))
    await store.discard_pending(42)
    bundle = await store.get(42)
    assert bundle is not None
    assert bundle.pending_object is None
    assert len(bundle.objects) == 0


async def test_clear_removes_bundle() -> None:
    store = PassStore()
    await store.put(42, _bundle())
    await store.clear(42)
    assert await store.get(42) is None


async def test_add_object_noop_when_no_bundle() -> None:
    store = PassStore()
    await store.add_object(99, _obj())  # no crash
    assert await store.get(99) is None
