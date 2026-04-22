"""Cross-cutting handler utilities — safety decorator + error reply text.

``@safe_handler`` wraps every Telegram-facing handler so an unexpected
exception becomes a generic user reply rather than propagating into
FastAPI. The real exception is captured server-side via
:func:`logging.Logger.exception`, never surfaced to the user (which could
leak API keys, prompts, or request metadata).
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Awaitable, Callable

_logger = logging.getLogger(__name__)

GENERIC_ERROR_REPLY = "Something went wrong processing that. Please try again."


def safe_handler[**P, R](
    fn: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R | None]]:
    """Decorator: catch any Exception, log it, send a generic reply.

    Assumes the wrapped handler's first two positional args are
    ``(chat_id: int, client: TelegramClientProtocol, ...)``. The decorator
    never re-raises — webhook entry points must always return cleanly.
    """

    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | None:
        try:
            return await fn(*args, **kwargs)
        except Exception:
            _logger.exception("handler failed: %s", fn.__name__)
            try:
                chat_id = args[0] if args else kwargs.get("chat_id")
                client = args[1] if len(args) > 1 else kwargs.get("client")
                if isinstance(chat_id, int) and client is not None and hasattr(client, "send_text"):
                    await client.send_text(chat_id, GENERIC_ERROR_REPLY)
            except Exception:
                _logger.exception("safe_handler fallback reply failed")
            return None

    return wrapper
