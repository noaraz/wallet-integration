"""Tests for the vision_service facade — factories + swap point."""

from __future__ import annotations

from wallet_bot.services import vision_service
from wallet_bot.services.vision_service import (
    TextDumpProtocol,
    VisionExtractionError,
    VisionServiceProtocol,
    create_default_service,
    create_default_text_dumper,
)


def test_vision_extraction_error_is_exception() -> None:
    assert issubclass(VisionExtractionError, Exception)


def test_create_default_service_returns_protocol_impl(monkeypatch) -> None:
    sentinel = object()

    monkeypatch.setattr(
        "wallet_bot.services.gemini_vision.build_client",
        lambda api_key: sentinel,
    )
    svc = create_default_service("fake-key")

    assert isinstance(svc, VisionServiceProtocol)
    assert hasattr(svc, "extract")


def test_create_default_text_dumper_returns_protocol_impl(monkeypatch) -> None:
    sentinel = object()

    monkeypatch.setattr(
        "wallet_bot.services.gemini_vision.build_client",
        lambda api_key: sentinel,
    )
    dumper = create_default_text_dumper("fake-key")

    assert isinstance(dumper, TextDumpProtocol)
    assert hasattr(dumper, "dump_file")


def test_facade_re_exports_error() -> None:
    # Callers must never need to import gemini_vision directly for the error.
    assert vision_service.VisionExtractionError is VisionExtractionError
