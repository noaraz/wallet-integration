"""Inline-button callback handler — routes callback_query to bundle flow."""

from __future__ import annotations

import json
import logging
import re

from wallet_bot.handlers._render import field_prompt, label_for
from wallet_bot.handlers._safe import safe_handler
from wallet_bot.models.callback_ids import (
    EDIT_FIELD_TO_TICKET_ATTR,
    CallbackId,
    parse_callback_id,
)
from wallet_bot.models.ticket import ExtractedTicket
from wallet_bot.models.wallet import PassBundle
from wallet_bot.services.draft_store import DraftStore
from wallet_bot.services.pass_store import PassStore
from wallet_bot.services.telegram_client import InlineButton, TelegramClientProtocol
from wallet_bot.services.wallet_service import WalletServiceProtocol

_logger = logging.getLogger(__name__)
_CANCELLED_MSG = "Cancelled."


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_exact_match(ticket: ExtractedTicket, bundle: PassBundle) -> bool:
    return _normalize(ticket.event_name or "") == _normalize(bundle.event_name) and (
        _normalize(ticket.date or "") == _normalize(bundle.date)
    )


def _is_close_match(ticket: ExtractedTicket, bundle: PassBundle) -> bool:
    """Date matches exactly but event name differs after normalization."""
    return _normalize(ticket.date or "") == _normalize(bundle.date) and (
        _normalize(ticket.event_name or "") != _normalize(bundle.event_name)
    )


def _event_label(ticket: ExtractedTicket) -> str:
    parts = [ticket.event_name or "?", ticket.date or "?"]
    return " · ".join(p for p in parts if p != "?") or "this event"


@safe_handler
async def handle_callback(
    chat_id: int,
    client: TelegramClientProtocol,
    *,
    callback_query_id: str,
    callback_data: str,
    store: DraftStore,
    pass_store: PassStore | None = None,
    wallet_service: WalletServiceProtocol | None = None,
) -> None:
    await client.answer_callback_query(callback_query_id=callback_query_id)

    cb = parse_callback_id(callback_data)
    if cb is None:
        _logger.info("dropped unknown callback_data from chat_id=%s", chat_id)
        return

    # ── WALLET_GET_LINK ────────────────────────────────────────────────────────
    if cb is CallbackId.WALLET_GET_LINK:
        if pass_store is None or wallet_service is None:
            return
        bundle = await pass_store.get(chat_id)
        if bundle is None or not bundle.objects:
            await client.send_text(chat_id, "No active bundle. Send a ticket photo first.")
            return
        save_url = await wallet_service.build_save_url(bundle.objects)
        await client.send_url_button(
            chat_id, "Your pass is ready!", "Add to Google Wallet", save_url
        )
        await pass_store.clear(chat_id)
        return

    # ── WALLET_BUNDLE_YES ──────────────────────────────────────────────────────
    if cb is CallbackId.WALLET_BUNDLE_YES:
        if pass_store is None:
            return
        bundle = await pass_store.get(chat_id)
        if bundle is None or bundle.pending_object is None:
            return
        await pass_store.confirm_pending(chat_id)
        updated = await pass_store.get(chat_id)
        n = len(updated.objects) if updated else 1
        await client.send_with_inline_keyboard(
            chat_id,
            f"Added · bundle now has {n} tickets for {bundle.event_name} · {bundle.date}.",
            rows=[[InlineButton(text="Get Wallet link", callback_data=CallbackId.WALLET_GET_LINK)]],
        )
        return

    # ── WALLET_BUNDLE_NO ───────────────────────────────────────────────────────
    if cb is CallbackId.WALLET_BUNDLE_NO:
        if pass_store is None:
            return
        await pass_store.discard_pending(chat_id)
        await client.send_text(chat_id, "Ticket ignored.")
        return

    # ── Existing draft callbacks ───────────────────────────────────────────────
    draft = await store.get(chat_id)
    if draft is None:
        return

    if cb is CallbackId.APPROVE:
        ticket = draft.ticket

        if wallet_service is None or pass_store is None:
            await store.clear(chat_id)
            await client.send_text(
                chat_id,
                "Wallet not configured. Set WALLET_ISSUER_ID and WALLET_SA_JSON.",
            )
            return

        _logger.info(
            "ticket_approved %s",
            json.dumps(
                ticket.model_dump(exclude={"raw_text": True, "barcode": {"barcode_value"}}),
                ensure_ascii=False,
            ),
        )

        # Build BEFORE clearing draft — a build failure leaves draft intact for retry.
        wallet_obj = wallet_service.build_object(chat_id, ticket)
        await store.clear(chat_id)
        bundle = await pass_store.get(chat_id)

        if bundle is None:
            await pass_store.put(
                chat_id,
                PassBundle(
                    event_name=ticket.event_name or "",
                    date=ticket.date or "",
                    class_id=wallet_obj.class_id,
                    objects=[wallet_obj],
                ),
            )
            label = _event_label(ticket)
            await client.send_with_inline_keyboard(
                chat_id,
                f"Saved ✓ for {label}.\nSend more tickets for this event, or tap below.",
                rows=[
                    [InlineButton(text="Get Wallet link", callback_data=CallbackId.WALLET_GET_LINK)]
                ],
            )
            return

        if _is_exact_match(ticket, bundle):
            if wallet_obj.barcode_value and await pass_store.has_barcode(
                chat_id, wallet_obj.barcode_value
            ):
                await client.send_text(chat_id, "This ticket is already in your bundle.")
                return
            await pass_store.add_object(chat_id, wallet_obj)
            updated = await pass_store.get(chat_id)
            n = len(updated.objects) if updated else 1
            label = _event_label(ticket)
            await client.send_with_inline_keyboard(
                chat_id,
                f"Added · bundle now has {n} tickets for {label}.",
                rows=[
                    [InlineButton(text="Get Wallet link", callback_data=CallbackId.WALLET_GET_LINK)]
                ],
            )
            return

        if _is_close_match(ticket, bundle):
            await pass_store.set_pending(chat_id, wallet_obj)
            await client.send_with_inline_keyboard(
                chat_id,
                f"Is this the same event as {bundle.event_name} on {bundle.date}?",
                rows=[
                    [
                        InlineButton(
                            text="Yes, add to bundle", callback_data=CallbackId.WALLET_BUNDLE_YES
                        ),
                        InlineButton(text="No, ignore", callback_data=CallbackId.WALLET_BUNDLE_NO),
                    ]
                ],
            )
            return

        label = _event_label(ticket)
        await client.send_text(
            chat_id,
            f"This ticket is for {label}, but your bundle is for "
            f"{bundle.event_name} · {bundle.date}. Ticket ignored.",
        )
        return

    if cb is CallbackId.CANCEL:
        await store.clear(chat_id)
        await client.send_text(chat_id, _CANCELLED_MSG)
        return

    attr = EDIT_FIELD_TO_TICKET_ATTR[cb]
    await store.set_editing_field(chat_id, attr)
    label = label_for(cb) or attr
    await client.send_force_reply(chat_id=chat_id, text=field_prompt(label))
