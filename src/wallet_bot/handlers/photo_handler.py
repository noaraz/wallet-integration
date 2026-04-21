"""Handler for photo messages."""

from __future__ import annotations

from telegram import Update

from wallet_bot.services.telegram_client import TelegramClientProtocol

_TEXT = "Got it, processing…"


async def handle_photo(update: Update, client: TelegramClientProtocol) -> None:
    assert update.effective_chat is not None
    await client.send_text(update.effective_chat.id, _TEXT)
