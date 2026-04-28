"""Handler for the /help command."""

from __future__ import annotations

from wallet_bot.services.telegram_client import TelegramClientProtocol

_TEXT = (
    "Available commands:\n"
    "/start — show welcome message\n"
    "/help — show this message\n\n"
    "Send a ticket photo to generate a Google Wallet pass.\n\n"
    "Multi-ticket bundles: send multiple photos for the same event, "
    "approve each ticket, then tap Get Wallet link to add them all at once."
)


async def handle_help(chat_id: int, client: TelegramClientProtocol) -> None:
    await client.send_text(chat_id, _TEXT)
