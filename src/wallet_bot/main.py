"""FastAPI application — webhook handler and DI wiring."""

from __future__ import annotations

import hmac
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from telegram import Bot, Update

from wallet_bot.config import Settings, get_settings
from wallet_bot.handlers.help_handler import handle_help
from wallet_bot.handlers.photo_handler import handle_photo
from wallet_bot.handlers.start_handler import handle_start
from wallet_bot.services.telegram_client import TelegramClient, TelegramClientProtocol


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()  # fails fast if any required env var is missing
    bot = Bot(token=settings.bot_token.get_secret_value())
    app.state.bot = bot
    app.state.telegram_client = TelegramClient(bot)
    yield


app = FastAPI(lifespan=lifespan)


def get_client(request: Request) -> TelegramClientProtocol:
    return request.app.state.telegram_client  # type: ignore[no-any-return]


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


async def _dispatch(
    cmd: str | None,
    has_photo: bool,
    chat_id: int,
    client: TelegramClientProtocol,
) -> None:
    """Route a parsed update to the appropriate handler."""
    if cmd == "/start":
        await handle_start(chat_id, client)
    elif cmd == "/help":
        await handle_help(chat_id, client)
    elif has_photo:
        await handle_photo(chat_id, client)


@app.post("/telegram/webhook", status_code=200)
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
    client: TelegramClientProtocol = Depends(get_client),
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

    msg = update.message
    if msg is None:
        return {"ok": "true"}

    if update.effective_chat is None:
        return {"ok": "true"}

    chat_id = update.effective_chat.id

    # Strip @botname suffix so `/start@walletbot` matches `/start`.
    parts = msg.text.split() if msg.text else []
    cmd = parts[0].split("@")[0] if parts else None

    await _dispatch(cmd, bool(msg.photo), chat_id, client)

    return {"ok": "true"}
