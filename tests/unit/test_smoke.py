"""Smoke test — scaffold sanity check. Phases replace with real tests."""

from __future__ import annotations

from wallet_bot.main import healthz


def test_healthz_returns_ok() -> None:
    assert healthz() == {"status": "ok"}
