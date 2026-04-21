"""Structural tests for TelegramClientProtocol."""

from __future__ import annotations

import inspect


def test_protocol_has_send_text_with_correct_signature() -> None:
    """TelegramClientProtocol must expose send_text(chat_id, text)."""
    from wallet_bot.services.telegram_client import TelegramClientProtocol

    assert hasattr(TelegramClientProtocol, "send_text")
    sig = inspect.signature(TelegramClientProtocol.send_text)
    params = list(sig.parameters)
    assert "chat_id" in params
    assert "text" in params
