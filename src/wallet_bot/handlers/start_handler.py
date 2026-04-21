"""Handler for the /start command."""

from __future__ import annotations

from wallet_bot.services.telegram_client import TelegramClientProtocol

_TEXT = (
    "Welcome to Wallet Bot!\n\n"
    "Send me a photo of your ticket and I'll convert it to a Google Wallet pass."
)


async def handle_start(chat_id: int, client: TelegramClientProtocol) -> None:
    await client.send_text(chat_id, _TEXT)
