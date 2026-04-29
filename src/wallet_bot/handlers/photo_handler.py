"""Photo-message handler — download, extract, decode barcode, render draft.

Flow:
    1. Download the photo bytes from Telegram.
    2. Ask the vision service for a structured ``ExtractedTicket`` (text fields only).
    3. Ask the barcode decoder for the machine-readable payload; merge into the ticket.
    4. Store the draft in :class:`DraftStore` keyed by chat_id.
    5. Post a message with all fields + inline keyboard for editing.

Any failure along the way is caught by ``@safe_handler`` and replaces
the flow with a generic reply; no backend details ever reach the user.
"""

from __future__ import annotations

from datetime import UTC, datetime

from wallet_bot.handlers._render import render_draft
from wallet_bot.handlers._safe import safe_handler
from wallet_bot.handlers._typing import typing_indicator
from wallet_bot.models.ticket import DraftState
from wallet_bot.services.barcode_service import BarcodeDecoderProtocol
from wallet_bot.services.draft_store import DraftStore
from wallet_bot.services.telegram_client import TelegramClientProtocol
from wallet_bot.services.vision_service import VisionServiceProtocol


@safe_handler
async def handle_photo(
    chat_id: int,
    client: TelegramClientProtocol,
    *,
    file_id: str,
    vision: VisionServiceProtocol,
    decoder: BarcodeDecoderProtocol,
    store: DraftStore,
) -> None:
    # The Gemini call routinely takes 5-15 s. Show a refreshing "typing..."
    # indicator so the user sees immediate feedback that the bot received
    # the photo and is working on it.
    async with typing_indicator(client, chat_id):
        image_bytes, mime = await client.download_photo_bytes(file_id=file_id)
        ticket = await vision.extract(image_bytes, mime_type=mime)
        ticket.barcode = await decoder.decode(image_bytes)

    text, rows = render_draft(ticket)
    message_id = await client.send_with_inline_keyboard(
        chat_id=chat_id,
        text=text,
        rows=rows,
    )

    await store.put(
        chat_id,
        DraftState(
            ticket=ticket,
            message_id=message_id,
            created_at=datetime.now(tz=UTC),
        ),
    )
