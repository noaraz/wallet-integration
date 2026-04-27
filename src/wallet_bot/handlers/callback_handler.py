"""Inline-button callback handler.

Routes an already-authorised ``callback_query`` to the right action:

* Unknown / malformed ``callback_data`` → answer the query (stop the
  Telegram spinner) and do nothing else. No draft state is mutated.
* ``edit_*`` → mark the draft's ``editing_field`` and send a ForceReply
  prompting the user for the new value. The actual edit is applied in
  :mod:`wallet_bot.handlers.edit_reply_handler` when the text arrives.
* ``approve`` → log the approved ticket as JSON (excluding ``raw_text``)
  at INFO level; clear the draft; reply with a confirmation.
* ``cancel`` → clear the draft; reply "Cancelled."
"""

from __future__ import annotations

import json
import logging

from wallet_bot.handlers._render import field_prompt, label_for
from wallet_bot.handlers._safe import safe_handler
from wallet_bot.models.callback_ids import (
    EDIT_FIELD_TO_TICKET_ATTR,
    CallbackId,
    parse_callback_id,
)
from wallet_bot.services.draft_store import DraftStore
from wallet_bot.services.telegram_client import TelegramClientProtocol

_logger = logging.getLogger(__name__)

_APPROVED_MSG = "Got it! Pass generation coming in Phase 04."
_CANCELLED_MSG = "Cancelled."


@safe_handler
async def handle_callback(
    chat_id: int,
    client: TelegramClientProtocol,
    *,
    callback_query_id: str,
    callback_data: str,
    store: DraftStore,
) -> None:
    # Always ack the query first so the Telegram spinner stops — even for
    # unknown callback_data we don't want to leave the user hanging.
    await client.answer_callback_query(callback_query_id=callback_query_id)

    cb = parse_callback_id(callback_data)
    if cb is None:
        _logger.info("dropped unknown callback_data from chat_id=%s", chat_id)
        return

    draft = await store.get(chat_id)
    if draft is None:
        return

    if cb is CallbackId.APPROVE:
        payload = draft.ticket.model_dump(exclude={"raw_text"})
        # INFO-level structured log — Cloud Logging picks this up.
        _logger.info("ticket_approved %s", json.dumps(payload, ensure_ascii=False))
        await store.clear(chat_id)
        await client.send_text(chat_id, _APPROVED_MSG)
        return

    if cb is CallbackId.CANCEL:
        await store.clear(chat_id)
        await client.send_text(chat_id, _CANCELLED_MSG)
        return

    # Remaining cases are EDIT_* buttons.
    attr = EDIT_FIELD_TO_TICKET_ATTR[cb]
    await store.set_editing_field(chat_id, attr)
    label = label_for(cb) or attr
    await client.send_force_reply(chat_id=chat_id, text=field_prompt(label))
    # Note: we deliberately do NOT re-render the draft message here. The
    # contents haven't changed (only the in-memory editing_field has),
    # and Telegram's edit_message_text rejects no-op edits with
    # ``BadRequest: Message is not modified``. The keyboard stays live
    # on the original message; the ForceReply prompt is the visible cue.
