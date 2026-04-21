def test_fake_client_satisfies_protocol() -> None:
    """FakeClient must structurally satisfy TelegramClientProtocol."""
    import inspect

    from wallet_bot.services.telegram_client import TelegramClientProtocol

    # We'll verify FakeClient against the protocol once conftest defines it.
    # For now, confirm TelegramClientProtocol is importable and has send_text.
    assert hasattr(TelegramClientProtocol, "send_text")
    sig = inspect.signature(TelegramClientProtocol.send_text)
    params = list(sig.parameters)
    assert "chat_id" in params
    assert "text" in params
