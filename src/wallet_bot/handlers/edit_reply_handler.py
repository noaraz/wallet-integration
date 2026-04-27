"""Text-reply handler — applies the user's correction to the draft field.

Invoked only when the chat has a draft with a non-None ``editing_field``.
Empty text is ignored (keeps editing state so the user can try again).
"""

from __future__ import annotations

from wallet_bot.handlers._render import render_draft
from wallet_bot.handlers._safe import safe_handler
from wallet_bot.handlers._typing import typing_indicator
from wallet_bot.services.draft_store import DraftStore
from wallet_bot.services.telegram_client import TelegramClientProtocol


@safe_handler
async def handle_edit_reply(
    chat_id: int,
    client: TelegramClientProtocol,
    *,
    text: str,
    store: DraftStore,
) -> None:
    draft = await store.get(chat_id)
    if draft is None or draft.editing_field is None:
        return

    value = text.strip()
    if not value:
        return

    field = draft.editing_field
    # Fast path (no Gemini), but a "typing…" tick gives an immediate
    # "got your reply" signal while the edit_message_text round-trip runs.
    async with typing_indicator(client, chat_id):
        await store.apply_edit(chat_id, field, value)

        updated = await store.get(chat_id)
        if updated is None:
            return
        new_text, rows = render_draft(updated.ticket)
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=updated.message_id,
            text=new_text,
            rows=rows,
        )
