"""Handler for photo messages."""

from __future__ import annotations

from wallet_bot.services.telegram_client import TelegramClientProtocol

_TEXT = "Got it, processing…"


async def handle_photo(chat_id: int, client: TelegramClientProtocol) -> None:
    await client.send_text(chat_id, _TEXT)
