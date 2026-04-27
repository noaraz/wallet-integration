"""FastAPI application — webhook handler and DI wiring.

Wires the Phase-02 routes:

* ``/start``, ``/help`` — Phase-01 commands (unchanged)
* Photo in a private chat → download → Gemini Vision → editable draft
* ``callback_query`` (inline-button tap) → :func:`handle_callback`
* Text in private chat while a draft is in edit-mode → :func:`handle_edit_reply`
* Anything in a non-private chat → one-shot "DM only" reply

The vision service is created *lazily* on the first webhook call rather than
in ``lifespan``.  This keeps tests able to monkey-patch
``wallet_bot.main.create_default_service`` after the FastAPI app has started
up.  Lifespan still handles the cheap, always-needed objects (``Bot`` +
``TelegramClient``).
"""

from __future__ import annotations

import hmac
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from telegram import Bot, Update

from wallet_bot.config import Settings, get_settings
from wallet_bot.handlers.callback_handler import handle_callback
from wallet_bot.handlers.edit_reply_handler import handle_edit_reply
from wallet_bot.handlers.help_handler import handle_help
from wallet_bot.handlers.photo_handler import handle_photo
from wallet_bot.handlers.start_handler import handle_start
from wallet_bot.services.draft_store import DraftStore, get_default_store
from wallet_bot.services.telegram_client import TelegramClient, TelegramClientProtocol
from wallet_bot.services.vision_service import (
    VisionServiceProtocol,
    create_default_service,
)

# Default to INFO so handler logs are visible in `docker compose` output.
# basicConfig is a no-op if logging was already configured (e.g. in tests).
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
_logger = logging.getLogger(__name__)

_DM_ONLY_REPLY = "This bot only works in private DMs."


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()  # fails fast if any required env var is missing
    bot = Bot(token=settings.bot_token.get_secret_value())
    app.state.bot = bot
    app.state.telegram_client = TelegramClient(bot)
    app.state.draft_store = get_default_store()
    # Lazily built on first webhook call so tests can monkey-patch
    # ``create_default_service`` *after* startup.
    app.state.vision_service = None
    yield


app = FastAPI(lifespan=lifespan)


def get_client(request: Request) -> TelegramClientProtocol:
    return request.app.state.telegram_client  # type: ignore[no-any-return]


def get_store(request: Request) -> DraftStore:
    return request.app.state.draft_store  # type: ignore[no-any-return]


def get_vision(request: Request, settings: Settings) -> VisionServiceProtocol:
    svc = request.app.state.vision_service
    if svc is None:
        svc = create_default_service(
            settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
        )
        request.app.state.vision_service = svc
    return svc  # type: ignore[no-any-return]


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _largest_photo_file_id(photo_sizes: list) -> str | None:  # type: ignore[type-arg]
    if not photo_sizes:
        return None
    largest = max(photo_sizes, key=lambda p: (p.width or 0) * (p.height or 0))
    return str(largest.file_id)


@app.post("/telegram/webhook", status_code=200)
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
    client: TelegramClientProtocol = Depends(get_client),
    store: DraftStore = Depends(get_store),
) -> dict[str, str]:
    expected = settings.webhook_secret.get_secret_value()
    received = x_telegram_bot_api_secret_token or ""
    if not hmac.compare_digest(received, expected):
        raise HTTPException(status_code=403)

    body = await request.json()
    bot: Bot = request.app.state.bot
    update = Update.de_json(body, bot)  # type: ignore[arg-type]

    if update.effective_user is None:
        return {"ok": "true"}

    if update.effective_user.id not in settings.allowed_tg_user_ids:
        raise HTTPException(status_code=403)

    if update.effective_chat is None:
        return {"ok": "true"}

    chat_id = update.effective_chat.id

    # --- Callback query (inline-button tap) -----------------------------------
    cbq = update.callback_query
    if cbq is not None:
        _logger.info("update: callback_query data=%r chat=%s", cbq.data, chat_id)
        # Non-private chats: drop silently (keyboard should never have been
        # visible in a group anyway).
        if cbq.message is not None and cbq.message.chat.type != "private":
            return {"ok": "true"}
        await handle_callback(
            chat_id=chat_id,
            client=client,
            callback_query_id=cbq.id,
            callback_data=cbq.data or "",
            store=store,
        )
        return {"ok": "true"}

    # --- Message updates ------------------------------------------------------
    msg = update.message
    if msg is None:
        _logger.info("update: no message, no callback (ignored) chat=%s", chat_id)
        return {"ok": "true"}

    _logger.info(
        "update: message chat=%s photo=%s text=%r",
        chat_id,
        bool(msg.photo),
        (msg.text[:80] if msg.text else None),
    )

    # DM-only: reject photos/text in group/supergroup/channel with one-shot
    # reply and do NOT invoke any downstream handler.
    if update.effective_chat.type != "private":
        if msg.photo or msg.text:
            await client.send_text(chat_id, _DM_ONLY_REPLY)
        return {"ok": "true"}

    # Photo → vision extraction.
    if msg.photo:
        file_id = _largest_photo_file_id(list(msg.photo))
        if file_id is None:
            return {"ok": "true"}
        vision = get_vision(request, settings)
        await handle_photo(
            chat_id=chat_id,
            client=client,
            file_id=file_id,
            vision=vision,
            store=store,
        )
        return {"ok": "true"}

    # Text: either a command, or a reply to a pending edit prompt.
    if msg.text:
        parts = msg.text.split()
        cmd = parts[0].split("@")[0] if parts else None
        if cmd == "/start":
            await handle_start(chat_id, client)
            return {"ok": "true"}
        if cmd == "/help":
            await handle_help(chat_id, client)
            return {"ok": "true"}

        draft = await store.get(chat_id)
        _logger.info(
            "text routing: draft=%s editing_field=%s",
            "yes" if draft else "no",
            draft.editing_field if draft else None,
        )
        if draft is not None and draft.editing_field is not None:
            await handle_edit_reply(
                chat_id=chat_id,
                client=client,
                text=msg.text,
                store=store,
            )
            return {"ok": "true"}

    return {"ok": "true"}
