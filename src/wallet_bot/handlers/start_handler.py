"""Handler for the /start command."""

from __future__ import annotations

from wallet_bot.services.telegram_client import TelegramClientProtocol

_TEXT = (
    "Welcome to Wallet Bot!\n\n"
    "Send me a photo of your event ticket and I'll convert it to a Google Wallet pass.\n\n"
    "How it works:\n"
    "1. Send a ticket photo\n"
    "2. Review the extracted details — edit any field if needed\n"
    "3. Tap Approve\n"
    "4. For the same event, send more ticket photos and approve each one\n"
    "5. Tap Get Wallet link to add all your tickets to Google Wallet in one tap"
)


async def handle_start(chat_id: int, client: TelegramClientProtocol) -> None:
    await client.send_text(chat_id, _TEXT)
