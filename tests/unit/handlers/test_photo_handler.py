"""Tests for handle_photo — download → extract → render draft with keyboard."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from wallet_bot.handlers._safe import GENERIC_ERROR_REPLY
from wallet_bot.handlers.photo_handler import handle_photo
from wallet_bot.models.ticket import ExtractedTicket
from wallet_bot.services.draft_store import DraftStore
from wallet_bot.services.vision_service import VisionExtractionError


class _FakeVision:
    def __init__(self, result: ExtractedTicket | Exception) -> None:
        self._result = result
        self.calls: list[tuple[bytes, str]] = []

    async def extract(self, image_bytes: bytes, mime_type: str) -> ExtractedTicket:
        self.calls.append((image_bytes, mime_type))
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


@pytest.fixture
def store() -> DraftStore:
    return DraftStore()


async def test_happy_path_stores_draft_and_sends_keyboard(fake_client, store) -> None:
    ticket = ExtractedTicket(event_name="גיא מזיג", price="₪134")
    vision = _FakeVision(ticket)

    await handle_photo(
        chat_id=42,
        client=fake_client,
        file_id="PHOTO123",
        vision=vision,
        store=store,
    )

    # Downloaded bytes were passed to the vision service.
    assert fake_client.downloaded == ["PHOTO123"]
    assert vision.calls[0][1] == "image/jpeg"

    # Rendered draft was sent with an inline keyboard.
    assert len(fake_client.sent_with_keyboard) == 1
    chat_id, text, rows = fake_client.sent_with_keyboard[0]
    assert chat_id == 42
    assert "גיא מזיג" in text
    assert rows  # not empty

    # Draft stored for callback handlers to pick up.
    draft = await store.get(42)
    assert draft is not None
    assert draft.ticket.event_name == "גיא מזיג"


async def test_vision_error_replies_generically(fake_client, store) -> None:
    vision = _FakeVision(VisionExtractionError("backend down"))

    await handle_photo(
        chat_id=1,
        client=fake_client,
        file_id="X",
        vision=vision,
        store=store,
    )

    # Generic fallback reply — no VisionExtractionError message leaked.
    assert (1, GENERIC_ERROR_REPLY) in fake_client.sent
    # No keyboard sent.
    assert fake_client.sent_with_keyboard == []
    # No draft stored.
    assert await store.get(1) is None


async def test_download_failure_replies_generically(store) -> None:
    from tests.conftest import FakeClient

    client = FakeClient()
    client.download_photo_bytes = AsyncMock(side_effect=RuntimeError("TG down"))  # type: ignore[method-assign]

    vision = _FakeVision(ExtractedTicket())
    await handle_photo(chat_id=1, client=client, file_id="X", vision=vision, store=store)

    assert (1, GENERIC_ERROR_REPLY) in client.sent
    assert client.sent_with_keyboard == []
