"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


class FakeClient:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_text(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient()
