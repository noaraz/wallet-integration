"""Telegram Bot client — thin wrapper over PTB's Bot."""

from __future__ import annotations

from typing import Protocol

from telegram import Bot


class TelegramClientProtocol(Protocol):
    async def send_text(self, chat_id: int, text: str) -> None: ...


class TelegramClient:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send_text(self, chat_id: int, text: str) -> None:
        await self._bot.send_message(chat_id=chat_id, text=text)
