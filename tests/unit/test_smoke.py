"""Smoke test — verifies the healthz endpoint responds."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_healthz_function_returns_ok():
    from wallet_bot.main import healthz

    result = await healthz()
    assert result == {"status": "ok"}
