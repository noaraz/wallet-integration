"""In-memory per-chat pass bundle store.

Tracks approved WalletObjects grouped by event for the multi-ticket bundle
flow. Mirrors DraftStore's locking pattern. No TTL in Phase 04 — the bundle
is cleared explicitly when the user taps "Get Wallet link".
"""

from __future__ import annotations

import asyncio

from wallet_bot.models.wallet import PassBundle, WalletObject


class PassStore:
    def __init__(self) -> None:
        self._data: dict[int, PassBundle] = {}
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock_for(self, chat_id: int) -> asyncio.Lock:
        if chat_id not in self._locks:
            self._locks[chat_id] = asyncio.Lock()
        return self._locks[chat_id]

    async def get(self, chat_id: int) -> PassBundle | None:
        async with self._lock_for(chat_id):
            return self._data.get(chat_id)

    async def put(self, chat_id: int, bundle: PassBundle) -> None:
        async with self._lock_for(chat_id):
            self._data[chat_id] = bundle

    async def add_object(self, chat_id: int, obj: WalletObject) -> None:
        async with self._lock_for(chat_id):
            bundle = self._data.get(chat_id)
            if bundle is None:
                return
            self._data[chat_id] = bundle.model_copy(update={"objects": [*bundle.objects, obj]})

    async def has_barcode(self, chat_id: int, barcode_value: str) -> bool:
        async with self._lock_for(chat_id):
            bundle = self._data.get(chat_id)
            if bundle is None:
                return False
            return bundle.has_barcode(barcode_value)

    async def set_pending(self, chat_id: int, obj: WalletObject) -> None:
        async with self._lock_for(chat_id):
            bundle = self._data.get(chat_id)
            if bundle is None:
                return
            self._data[chat_id] = bundle.model_copy(update={"pending_object": obj})

    async def confirm_pending(self, chat_id: int) -> None:
        async with self._lock_for(chat_id):
            bundle = self._data.get(chat_id)
            if bundle is None or bundle.pending_object is None:
                return
            self._data[chat_id] = bundle.model_copy(
                update={
                    "objects": [*bundle.objects, bundle.pending_object],
                    "pending_object": None,
                }
            )

    async def discard_pending(self, chat_id: int) -> None:
        async with self._lock_for(chat_id):
            bundle = self._data.get(chat_id)
            if bundle is None:
                return
            self._data[chat_id] = bundle.model_copy(update={"pending_object": None})

    async def clear(self, chat_id: int) -> None:
        async with self._lock_for(chat_id):
            self._data.pop(chat_id, None)
