"""In-memory per-chat draft store.

Pure state: no I/O, no framework types. Safe for concurrent access via a
per-chat :class:`asyncio.Lock`. TTL-evicts stale drafts on access and caps
total entries (LRU by ``created_at``) to bound memory.

Module-level singleton :func:`get_default_store` is used by the FastAPI DI
wiring so handlers share state across requests within the same process.
Phase 05 can swap the backing store without changing the public API.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from wallet_bot.models.ticket import DraftState, ExtractedTicket

_DEFAULT_TTL = timedelta(hours=1)
_DEFAULT_MAX_ENTRIES = 32


class DraftStore:
    def __init__(
        self,
        ttl: timedelta = _DEFAULT_TTL,
        max_entries: int = _DEFAULT_MAX_ENTRIES,
    ) -> None:
        self._ttl = ttl
        self._max_entries = max_entries
        self._data: dict[int, DraftState] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    def _lock_for(self, chat_id: int) -> asyncio.Lock:
        lock = self._locks.get(chat_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[chat_id] = lock
        return lock

    def _is_expired(self, draft: DraftState) -> bool:
        now = datetime.now(tz=UTC)
        return now - draft.created_at > self._ttl

    async def get(self, chat_id: int) -> DraftState | None:
        async with self._lock_for(chat_id):
            draft = self._data.get(chat_id)
            if draft is None:
                return None
            if self._is_expired(draft):
                self._data.pop(chat_id, None)
                return None
            return draft

    async def put(self, chat_id: int, draft: DraftState) -> None:
        async with self._lock_for(chat_id):
            self._data[chat_id] = draft
            self._enforce_cap(protect=chat_id)

    def _enforce_cap(self, protect: int) -> None:
        """LRU-evict oldest entries until size <= max_entries. Must hold lock."""
        while len(self._data) > self._max_entries:
            # Oldest by created_at, excluding the just-inserted chat.
            candidates = [cid for cid in self._data if cid != protect]
            if not candidates:
                return
            oldest = min(candidates, key=lambda cid: self._data[cid].created_at)
            self._data.pop(oldest, None)

    async def clear(self, chat_id: int) -> None:
        async with self._lock_for(chat_id):
            self._data.pop(chat_id, None)

    async def set_editing_field(self, chat_id: int, field: str) -> None:
        async with self._lock_for(chat_id):
            draft = self._data.get(chat_id)
            if draft is None:
                return
            self._data[chat_id] = draft.model_copy(update={"editing_field": field})

    async def apply_edit(self, chat_id: int, field: str, value: str) -> None:
        if field not in ExtractedTicket.model_fields or field == "raw_text":
            raise ValueError(f"unknown or forbidden ticket field: {field!r}")
        async with self._lock_for(chat_id):
            draft = self._data.get(chat_id)
            if draft is None:
                return
            new_ticket = draft.ticket.model_copy(update={field: value})
            self._data[chat_id] = draft.model_copy(
                update={"ticket": new_ticket, "editing_field": None},
            )


_default_store = DraftStore()


def get_default_store() -> DraftStore:
    """Return the process-wide default store (used by FastAPI DI)."""
    return _default_store
