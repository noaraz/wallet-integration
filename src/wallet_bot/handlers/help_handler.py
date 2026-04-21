"""Handler for the /help command."""

from __future__ import annotations

from telegram import Update

from wallet_bot.services.telegram_client import TelegramClientProtocol

_TEXT = (
    "Available commands:\n"
    "/start — show welcome message\n"
    "/help — show this message\n\n"
    "Send a ticket photo to generate a Google Wallet pass."
)


async def handle_help(update: Update, client: TelegramClientProtocol) -> None:
    assert update.effective_chat is not None
    await client.send_text(update.effective_chat.id, _TEXT)
