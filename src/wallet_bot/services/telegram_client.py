"""Telegram Bot client — thin wrapper over python-telegram-bot's Bot.

The wrapper keeps PTB types out of the rest of the codebase: handlers
receive and produce plain values (chat_id, text, message_id) and small
``InlineButton`` records. PTB types only appear here.

**Security note:** every outbound message leaves ``parse_mode`` unset
(i.e. plain text). Ticket content is user-supplied / OCR-derived and may
contain ``_``, ``*``, ``<``, etc.; enabling Markdown or HTML would open
parsing / injection issues for zero user benefit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from telegram import Bot, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup


@dataclass(frozen=True, slots=True)
class InlineButton:
    text: str
    callback_data: str


class TelegramClientProtocol(Protocol):
    async def send_text(self, chat_id: int, text: str) -> None: ...

    async def send_with_inline_keyboard(
        self,
        chat_id: int,
        text: str,
        rows: list[list[InlineButton]],
    ) -> int: ...

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        rows: list[list[InlineButton]],
    ) -> None: ...

    async def answer_callback_query(self, callback_query_id: str) -> None: ...

    async def send_force_reply(self, chat_id: int, text: str) -> int: ...

    async def download_photo_bytes(self, file_id: str) -> tuple[bytes, str]: ...

    async def send_chat_action(self, chat_id: int, action: str) -> None: ...

    async def send_url_button(
        self, chat_id: int, text: str, button_text: str, url: str
    ) -> None: ...


def _to_markup(rows: list[list[InlineButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text=b.text, callback_data=b.callback_data) for b in row]
            for row in rows
        ]
    )


class TelegramClient:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send_text(self, chat_id: int, text: str) -> None:
        await self._bot.send_message(chat_id=chat_id, text=text)

    async def send_with_inline_keyboard(
        self,
        chat_id: int,
        text: str,
        rows: list[list[InlineButton]],
    ) -> int:
        sent = await self._bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=_to_markup(rows),
        )
        return int(sent.message_id)

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        rows: list[list[InlineButton]],
    ) -> None:
        await self._bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=_to_markup(rows),
        )

    async def answer_callback_query(self, callback_query_id: str) -> None:
        await self._bot.answer_callback_query(callback_query_id=callback_query_id)

    async def send_force_reply(self, chat_id: int, text: str) -> int:
        sent = await self._bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=ForceReply(selective=True),
        )
        return int(sent.message_id)

    async def download_photo_bytes(self, file_id: str) -> tuple[bytes, str]:
        """Fetch a Telegram photo (PhotoSize → JPEG) and return (bytes, mime)."""
        tg_file = await self._bot.get_file(file_id=file_id)
        buf = await tg_file.download_as_bytearray()
        # Telegram compresses photos to JPEG regardless of what the user uploaded.
        return bytes(buf), "image/jpeg"

    async def send_chat_action(self, chat_id: int, action: str) -> None:
        """Show a transient status (e.g. ``"typing"``) in the chat header.

        Telegram displays the indicator for ~5 s, so callers performing a
        long operation should re-send periodically. The action types are
        listed at https://core.telegram.org/bots/api#sendchataction.
        """
        await self._bot.send_chat_action(chat_id=chat_id, action=action)

    async def send_url_button(self, chat_id: int, text: str, button_text: str, url: str) -> None:
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(text=button_text, url=url)]])
        await self._bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)
