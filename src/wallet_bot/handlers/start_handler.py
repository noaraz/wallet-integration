"""Handler for the /start command."""

from __future__ import annotations

from telegram import Update

from wallet_bot.services.telegram_client import TelegramClientProtocol

_TEXT = (
    "Welcome to Wallet Bot!\n\n"
    "Send me a photo of your ticket and I'll convert it to a Google Wallet pass."
)


async def handle_start(update: Update, client: TelegramClientProtocol) -> None:
    if update.effective_chat is None:
        return
    await client.send_text(update.effective_chat.id, _TEXT)
