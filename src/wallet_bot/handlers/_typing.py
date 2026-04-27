"""Async helper for showing a persistent ``"typing…"`` indicator.

Telegram's chat-action status auto-clears after ~5 s. Long-running
extractions (a Gemini Vision call can take 10-15 s) need a periodic
refresh — otherwise the user stares at silence and assumes the bot
hung. :func:`typing_indicator` is an async-context-manager that fires
the action immediately and then refreshes it every ``refresh_seconds``
until the wrapped block exits.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from wallet_bot.services.telegram_client import TelegramClientProtocol

_logger = logging.getLogger(__name__)

_REFRESH_SECONDS = 4.0  # < Telegram's ~5 s display window


@contextlib.asynccontextmanager
async def typing_indicator(
    client: TelegramClientProtocol,
    chat_id: int,
    *,
    action: str = "typing",
    refresh_seconds: float = _REFRESH_SECONDS,
) -> AsyncIterator[None]:
    """Show ``action`` in the chat header for the duration of the block.

    Failures inside the loop are logged but never propagate — the chat
    indicator is best-effort UX, not a correctness primitive.
    """

    async def _loop() -> None:
        try:
            while True:
                try:
                    await client.send_chat_action(chat_id, action)
                except Exception:  # pragma: no cover — best-effort
                    _logger.warning("send_chat_action loop failed", exc_info=True)
                await asyncio.sleep(refresh_seconds)
        except asyncio.CancelledError:
            return

    # Fire once up-front so the indicator appears immediately, no matter
    # how fast the wrapped block runs (also makes tests deterministic).
    try:
        await client.send_chat_action(chat_id, action)
        _logger.info("send_chat_action ok chat=%s action=%s", chat_id, action)
    except Exception:  # pragma: no cover — best-effort
        _logger.warning("initial send_chat_action failed", exc_info=True)

    task = asyncio.create_task(_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, BaseException):
            await task
