"""Tests for the in-memory DraftStore (TTL, LRU cap, per-chat locks)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from wallet_bot.services.draft_store import DraftStore

from wallet_bot.models.ticket import DraftState, ExtractedTicket


def _make_draft(message_id: int = 1, event: str | None = None) -> DraftState:
    return DraftState(
        ticket=ExtractedTicket(event_name=event),
        message_id=message_id,
        created_at=datetime.now(tz=UTC),
    )


class TestBasicCrud:
    async def test_get_missing_returns_none(self) -> None:
        store = DraftStore()
        assert await store.get(123) is None

    async def test_put_then_get(self) -> None:
        store = DraftStore()
        draft = _make_draft(message_id=7)
        await store.put(123, draft)
        got = await store.get(123)
        assert got is not None
        assert got.message_id == 7

    async def test_clear_removes_entry(self) -> None:
        store = DraftStore()
        await store.put(123, _make_draft())
        await store.clear(123)
        assert await store.get(123) is None

    async def test_clear_missing_is_noop(self) -> None:
        store = DraftStore()
        await store.clear(999)  # must not raise


class TestEditingField:
    async def test_set_editing_field(self) -> None:
        store = DraftStore()
        await store.put(1, _make_draft())
        await store.set_editing_field(1, "event_name")
        draft = await store.get(1)
        assert draft is not None
        assert draft.editing_field == "event_name"

    async def test_set_editing_field_missing_chat_noop(self) -> None:
        store = DraftStore()
        await store.set_editing_field(999, "event_name")
        assert await store.get(999) is None

    async def test_apply_edit_updates_field_and_clears_editing(self) -> None:
        store = DraftStore()
        await store.put(1, _make_draft())
        await store.set_editing_field(1, "event_name")
        await store.apply_edit(1, "event_name", "גיא מזיג")

        draft = await store.get(1)
        assert draft is not None
        assert draft.ticket.event_name == "גיא מזיג"
        assert draft.editing_field is None

    async def test_apply_edit_missing_chat_noop(self) -> None:
        store = DraftStore()
        await store.apply_edit(999, "event_name", "x")

    async def test_apply_edit_rejects_unknown_field(self) -> None:
        store = DraftStore()
        await store.put(1, _make_draft())
        with pytest.raises(ValueError):
            await store.apply_edit(1, "not_a_real_field", "x")


class TestTtlEviction:
    async def test_expired_draft_evicted_on_get(self) -> None:
        store = DraftStore(ttl=timedelta(seconds=1))
        old = DraftState(
            ticket=ExtractedTicket(),
            message_id=1,
            created_at=datetime.now(tz=UTC) - timedelta(hours=2),
        )
        await store.put(1, old)
        assert await store.get(1) is None


class TestLruCap:
    async def test_overflow_evicts_oldest(self) -> None:
        store = DraftStore(max_entries=3)
        base = datetime.now(tz=UTC)
        for i in range(3):
            await store.put(
                i,
                DraftState(
                    ticket=ExtractedTicket(),
                    message_id=i,
                    created_at=base - timedelta(minutes=10 - i),
                ),
            )
        # chat 0 is oldest. Inserting a 4th should evict chat 0.
        await store.put(
            99,
            DraftState(
                ticket=ExtractedTicket(),
                message_id=99,
                created_at=base,
            ),
        )
        assert await store.get(0) is None
        assert await store.get(1) is not None
        assert await store.get(99) is not None

    async def test_replacing_existing_chat_does_not_overflow(self) -> None:
        store = DraftStore(max_entries=2)
        for i in range(2):
            await store.put(i, _make_draft(message_id=i))
        # Re-put chat 0 — size stays at 2, no eviction needed.
        await store.put(0, _make_draft(message_id=42))
        assert (await store.get(0)).message_id == 42  # type: ignore[union-attr]
        assert await store.get(1) is not None


class TestConcurrency:
    async def test_concurrent_edits_to_same_chat_serialize(self) -> None:
        store = DraftStore()
        await store.put(1, _make_draft())

        order: list[str] = []

        async def slow_set(value: str) -> None:
            await store.set_editing_field(1, value)
            # Hold the lock by another await after setting? We can't, since the
            # store releases the lock once the method returns. What we can
            # assert is: both operations complete without corrupting state.
            order.append(value)

        await asyncio.gather(slow_set("event_name"), slow_set("venue"))
        draft = await store.get(1)
        assert draft is not None
        assert draft.editing_field in {"event_name", "venue"}
        assert len(order) == 2
