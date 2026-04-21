# Phase 01 — Telegram Webhook Skeleton Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a FastAPI webhook server that authenticates Telegram updates, enforces a user whitelist, and responds to `/start`, `/help`, and photo messages — deployed to Cloud Run `me-west1` as the bot's first live endpoint.

**Architecture:** Layered architecture — `main.py` owns routing and DI wiring; `handlers/` contains one thin async function per update type; `services/telegram_client.py` wraps PTB's `Bot` behind a protocol; `config.py` is a pydantic-settings `BaseSettings` subclass. All I/O is async. Everything runs in Docker.

**Tech Stack:** FastAPI 0.115+, python-telegram-bot 21+, pydantic-settings 2+, uvicorn, pytest-asyncio, httpx, asgi-lifespan.

**Spec:** `docs/superpowers/specs/2026-04-21-phase-01-telegram-webhook-design.md`

---

## File map

| File | Action | Responsibility |
|---|---|---|
| `src/wallet_bot/config.py` | Replace stub | `Settings` BaseSettings class + `get_settings()` |
| `src/wallet_bot/services/telegram_client.py` | Create | `TelegramClientProtocol` + `TelegramClient(Bot)` |
| `src/wallet_bot/handlers/__init__.py` | Create | empty |
| `src/wallet_bot/handlers/start_handler.py` | Create | `handle_start(update, client)` |
| `src/wallet_bot/handlers/help_handler.py` | Create | `handle_help(update, client)` |
| `src/wallet_bot/handlers/photo_handler.py` | Create | `handle_photo(update, client)` |
| `src/wallet_bot/main.py` | Replace stub | FastAPI app, lifespan, `/healthz`, `/telegram/webhook` |
| `src/wallet_bot/viewmodels/` | Delete | (replaced by `handlers/`) |
| `src/wallet_bot/views/` | Delete | (replaced by inline handler formatting) |
| `tests/conftest.py` | Extend | shared fixtures: `test_env`, `fake_client`, `test_app` |
| `tests/unit/test_config.py` | Create | Settings validation tests |
| `tests/unit/test_handlers.py` | Create | Handler unit tests with FakeClient |
| `tests/unit/test_webhook_auth.py` | Create | Webhook route auth tests |
| `pyproject.toml` | Modify | add runtime + dev deps; add `asyncio_default_fixture_loop_scope` |
| `Dockerfile` | Replace | multi-stage: `dev` target (docker compose) + `prod` target (Cloud Run) |
| `docker-compose.yml` | Modify | add `target: dev` |
| `.env.example` | Update | fix env var names to match Settings fields |
| `.claude/skills/deploy-cloud-run/SKILL.md` | Create | via `/superpowers:writing-skills` |
| `.claude/skills/tg-webhook-register/SKILL.md` | Create | via `/superpowers:writing-skills` |
| `phases/01-telegram-webhook/plan.md` | Fill in | link to this plan + phase checklist |
| `phases/01-telegram-webhook/CLAUDE.md` | Fill in | library choices + gotchas |
| `STATUS.md` | Update | Phase 01 ✅, Current Focus → Phase 02 |

---

## Chunk 1: Project setup

### Task 1: Create branch and add dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Create the feature branch**

```bash
git checkout main && git pull
git checkout -b feat/phase-01-telegram-webhook
```

- [ ] **Step 2: Update `pyproject.toml`**

Replace the `dependencies` and `dev` sections and add the pytest setting:

```toml
[project]
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "python-telegram-bot>=21.0,<22",
    "pydantic-settings>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5",
    "ruff>=0.5",
    "httpx>=0.27",
    "asgi-lifespan>=2.1",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
addopts = "-ra"
testpaths = ["tests"]
```

- [ ] **Step 3: Rebuild the Docker image**

```bash
docker compose build
```

Expected: last line should be something like `=> exporting to image` with no errors. Verify with:
```bash
docker compose run --rm bot python -c "import fastapi, telegram, pydantic_settings; print('deps ok')"
```
Expected output: `deps ok`

- [ ] **Step 4: Verify baseline test still passes**

```bash
docker compose run --rm bot pytest tests/unit/test_smoke.py -v
```

Expected: `test_healthz_returns_ok PASSED`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add Phase 01 runtime and dev dependencies"
```

---

### Task 2: Remove scaffold placeholder dirs

**Files:**
- Delete: `src/wallet_bot/viewmodels/__init__.py`
- Delete: `src/wallet_bot/views/__init__.py`

- [ ] **Step 1: Remove the empty placeholder dirs**

```bash
git rm src/wallet_bot/viewmodels/__init__.py
git rm src/wallet_bot/views/__init__.py
```

- [ ] **Step 2: Commit**

```bash
git commit -m "chore: remove viewmodels/ and views/ dirs (layered arch uses handlers/)"
```

---

## Chunk 2: Config layer

### Task 3: Write failing config tests

**Files:**
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for Settings validation."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from wallet_bot.config import Settings


def _make(monkeypatch, *, bot_token="tok", webhook_secret="sec", allowed="111"):
    monkeypatch.setenv("BOT_TOKEN", bot_token)
    monkeypatch.setenv("WEBHOOK_SECRET", webhook_secret)
    monkeypatch.setenv("ALLOWED_TG_USER_IDS", allowed)


def test_missing_bot_token(monkeypatch):
    _make(monkeypatch)
    monkeypatch.delenv("BOT_TOKEN")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_missing_webhook_secret(monkeypatch):
    _make(monkeypatch)
    monkeypatch.delenv("WEBHOOK_SECRET")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_empty_allowed_ids_raises(monkeypatch):
    _make(monkeypatch, allowed="")
    with pytest.raises(ValidationError, match="ALLOWED_TG_USER_IDS must not be empty"):
        Settings(_env_file=None)


def test_comma_separated_ids_parsed(monkeypatch):
    _make(monkeypatch, allowed="123,456")
    s = Settings(_env_file=None)
    assert s.allowed_tg_user_ids == [123, 456]


def test_single_id_parsed(monkeypatch):
    _make(monkeypatch, allowed="789")
    s = Settings(_env_file=None)
    assert s.allowed_tg_user_ids == [789]


def test_ids_with_spaces_parsed(monkeypatch):
    _make(monkeypatch, allowed="123 , 456 ")
    s = Settings(_env_file=None)
    assert s.allowed_tg_user_ids == [123, 456]
```

- [ ] **Step 2: Run to confirm RED**

```bash
docker compose run --rm bot pytest tests/unit/test_config.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `wallet_bot.config` has no `Settings` yet.

---

### Task 4: Implement `config.py`

**Files:**
- Modify: `src/wallet_bot/config.py`

- [ ] **Step 1: Write the implementation**

```python
"""Application settings — single source of truth for all config."""
from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: SecretStr           # env: BOT_TOKEN
    webhook_secret: SecretStr      # env: WEBHOOK_SECRET
    allowed_tg_user_ids: list[int] # env: ALLOWED_TG_USER_IDS (comma-separated)

    model_config = SettingsConfigDict(env_file=".env")

    @field_validator("allowed_tg_user_ids", mode="before")
    @classmethod
    def _parse_ids(cls, v: str | list[int]) -> list[int]:
        if isinstance(v, str):
            ids = [int(x.strip()) for x in v.split(",") if x.strip()]
            if not ids:
                raise ValueError("ALLOWED_TG_USER_IDS must not be empty")
            return ids
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 2: Run tests to confirm GREEN**

```bash
docker compose run --rm bot pytest tests/unit/test_config.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add src/wallet_bot/config.py tests/unit/test_config.py
git commit -m "feat: add Settings config with pydantic-settings"
```

---

## Chunk 3: Services — TelegramClient

### Task 5: Implement `services/telegram_client.py`

**Files:**
- Create: `src/wallet_bot/services/telegram_client.py`

- [ ] **Step 1: Write a failing structural test**

```python
# Add to tests/unit/test_handlers.py (temporarily at top, move to conftest later)
def test_fake_client_satisfies_protocol() -> None:
    """FakeClient must structurally satisfy TelegramClientProtocol."""
    from wallet_bot.services.telegram_client import TelegramClientProtocol
    from conftest import FakeClient  # will be importable after conftest is updated
    import inspect

    # Protocol has send_text — verify FakeClient has it with same signature
    assert hasattr(FakeClient, "send_text")
    sig = inspect.signature(FakeClient.send_text)
    params = list(sig.parameters)
    assert "chat_id" in params
    assert "text" in params
```

- [ ] **Step 2: Run to confirm RED**

```bash
docker compose run --rm bot pytest tests/unit/test_handlers.py::test_fake_client_satisfies_protocol -v
```

Expected: `ImportError` — `wallet_bot.services.telegram_client` does not exist yet.

- [ ] **Step 3: Write the implementation**

```python
"""Telegram Bot client — thin wrapper over PTB's Bot."""
from __future__ import annotations

from typing import Protocol

from telegram import Bot


class TelegramClientProtocol(Protocol):
    async def send_text(self, chat_id: int, text: str) -> None: ...


class TelegramClient:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send_text(self, chat_id: int, text: str) -> None:
        await self._bot.send_message(chat_id=chat_id, text=text)
```

- [ ] **Step 4: Run structural test to confirm GREEN**

```bash
docker compose run --rm bot python -c "from wallet_bot.services.telegram_client import TelegramClient, TelegramClientProtocol; print('ok')"
```

Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add src/wallet_bot/services/telegram_client.py
git commit -m "feat: add TelegramClient service and protocol"
```

---

## Chunk 4: Handlers

### Task 6: Write failing handler tests

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/unit/test_handlers.py`

- [ ] **Step 1: Add `FakeClient` to `tests/conftest.py`**

```python
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
```

- [ ] **Step 2: Write `tests/unit/test_handlers.py`**

```python
"""Unit tests for update handlers."""
from __future__ import annotations

import pytest
from telegram import Update

# Minimal Telegram Update payloads for testing
_USER_ID = 111222333
_CHAT_ID = 111222333


def _make_update(data: dict) -> Update:
    return Update.de_json(data, None)  # type: ignore[arg-type]


def _command_update(text: str, user_id: int = _USER_ID) -> Update:
    return _make_update({
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 1700000000,
            "chat": {"id": user_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "Test"},
            "text": text,
            "entities": [{"offset": 0, "length": len(text), "type": "bot_command"}],
        },
    })


def _photo_update(user_id: int = _USER_ID) -> Update:
    return _make_update({
        "update_id": 2,
        "message": {
            "message_id": 2,
            "date": 1700000000,
            "chat": {"id": user_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "Test"},
            "photo": [
                {
                    "file_id": "AABB",
                    "file_unique_id": "CCDD",
                    "width": 100,
                    "height": 100,
                    "file_size": 1024,
                }
            ],
        },
    })


@pytest.mark.asyncio
async def test_start_sends_welcome(fake_client):
    from wallet_bot.handlers.start_handler import handle_start

    await handle_start(_command_update("/start"), fake_client)

    assert len(fake_client.sent) == 1
    chat_id, text = fake_client.sent[0]
    assert chat_id == _CHAT_ID
    assert "welcome" in text.lower() or "wallet" in text.lower()


@pytest.mark.asyncio
async def test_help_sends_help_text(fake_client):
    from wallet_bot.handlers.help_handler import handle_help

    await handle_help(_command_update("/help"), fake_client)

    assert len(fake_client.sent) == 1
    chat_id, text = fake_client.sent[0]
    assert chat_id == _CHAT_ID
    assert "/start" in text or "/help" in text


@pytest.mark.asyncio
async def test_photo_sends_processing_ack(fake_client):
    from wallet_bot.handlers.photo_handler import handle_photo

    await handle_photo(_photo_update(), fake_client)

    assert len(fake_client.sent) == 1
    chat_id, text = fake_client.sent[0]
    assert chat_id == _CHAT_ID
    assert "processing" in text.lower()
```

- [ ] **Step 3: Run to confirm RED**

```bash
docker compose run --rm bot pytest tests/unit/test_handlers.py -v
```

Expected: `ImportError` — `wallet_bot.handlers` doesn't exist yet.

---

### Task 7: Implement handlers

**Files:**
- Create: `src/wallet_bot/handlers/__init__.py`
- Create: `src/wallet_bot/handlers/start_handler.py`
- Create: `src/wallet_bot/handlers/help_handler.py`
- Create: `src/wallet_bot/handlers/photo_handler.py`

- [ ] **Step 1: Create `handlers/__init__.py`**

```python
"""Telegram update handlers — one per update type."""
```

- [ ] **Step 2: Create `handlers/start_handler.py`**

```python
"""Handler for the /start command."""
from __future__ import annotations

from telegram import Update

from wallet_bot.services.telegram_client import TelegramClientProtocol

_TEXT = (
    "Welcome to Wallet Bot!\n\n"
    "Send me a photo of your ticket and I'll convert it to a Google Wallet pass."
)


async def handle_start(update: Update, client: TelegramClientProtocol) -> None:
    assert update.effective_chat is not None
    await client.send_text(update.effective_chat.id, _TEXT)
```

- [ ] **Step 3: Create `handlers/help_handler.py`**

```python
"""Handler for the /help command."""
from __future__ import annotations

from telegram import Update

from wallet_bot.services.telegram_client import TelegramClientProtocol

_TEXT = (
    "Available commands:\n"
    "/start — show welcome message\n"
    "/help — show this message\n\n"
    "Send a ticket photo to generate a Google Wallet pass."
)


async def handle_help(update: Update, client: TelegramClientProtocol) -> None:
    assert update.effective_chat is not None
    await client.send_text(update.effective_chat.id, _TEXT)
```

- [ ] **Step 4: Create `handlers/photo_handler.py`**

```python
"""Handler for photo messages."""
from __future__ import annotations

from telegram import Update

from wallet_bot.services.telegram_client import TelegramClientProtocol

_TEXT = "Got it, processing…"


async def handle_photo(update: Update, client: TelegramClientProtocol) -> None:
    assert update.effective_chat is not None
    await client.send_text(update.effective_chat.id, _TEXT)
```

- [ ] **Step 5: Run tests to confirm GREEN**

```bash
docker compose run --rm bot pytest tests/unit/test_handlers.py -v
```

Expected: all 3 handler tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/wallet_bot/handlers/ tests/conftest.py tests/unit/test_handlers.py
git commit -m "feat: add start, help, and photo handlers with FakeClient tests"
```

---

## Chunk 5: FastAPI app + webhook route

### Task 8: Write failing webhook auth tests

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/unit/test_webhook_auth.py`

- [ ] **Step 1: Extend `tests/conftest.py` with app fixtures**

Add below the existing `FakeClient` and `fake_client`:

```python
import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient


_WEBHOOK_SECRET = "test-webhook-secret"
_BOT_TOKEN = "123456:fake_token_for_tests"
_ALLOWED_USER_ID = 111222333


@pytest.fixture(autouse=False)
def test_env(monkeypatch):
    """Patch env vars and clear settings cache before each test that needs the app."""
    monkeypatch.setenv("BOT_TOKEN", _BOT_TOKEN)
    monkeypatch.setenv("WEBHOOK_SECRET", _WEBHOOK_SECRET)
    monkeypatch.setenv("ALLOWED_TG_USER_IDS", str(_ALLOWED_USER_ID))
    from wallet_bot.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def test_app(test_env, fake_client):
    """FastAPI app with lifespan running and client dependency overridden."""
    from wallet_bot.main import app, get_client

    app.dependency_overrides[get_client] = lambda: fake_client
    try:
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                yield client
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Write `tests/unit/test_webhook_auth.py`**

```python
"""Tests for webhook endpoint authentication and routing."""
from __future__ import annotations

import pytest

_SECRET = "test-webhook-secret"
_ALLOWED_ID = 111222333
_BLOCKED_ID = 999999999

_START_UPDATE = {
    "update_id": 1,
    "message": {
        "message_id": 1,
        "date": 1700000000,
        "chat": {"id": _ALLOWED_ID, "type": "private"},
        "from": {"id": _ALLOWED_ID, "is_bot": False, "first_name": "Test"},
        "text": "/start",
        "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
    },
}

_BLOCKED_UPDATE = {
    "update_id": 2,
    "message": {
        "message_id": 2,
        "date": 1700000000,
        "chat": {"id": _BLOCKED_ID, "type": "private"},
        "from": {"id": _BLOCKED_ID, "is_bot": False, "first_name": "Stranger"},
        "text": "/start",
        "entities": [{"offset": 0, "length": 6, "type": "bot_command"}],
    },
}


@pytest.mark.asyncio
async def test_missing_secret_header_returns_403(test_app):
    resp = await test_app.post("/telegram/webhook", json=_START_UPDATE)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_wrong_secret_returns_403(test_app):
    resp = await test_app.post(
        "/telegram/webhook",
        json=_START_UPDATE,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_whitelisted_user_returns_403(test_app):
    resp = await test_app.post(
        "/telegram/webhook",
        json=_BLOCKED_UPDATE,
        headers={"X-Telegram-Bot-Api-Secret-Token": _SECRET},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_whitelisted_user_with_valid_secret_returns_200(test_app):
    resp = await test_app.post(
        "/telegram/webhook",
        json=_START_UPDATE,
        headers={"X-Telegram-Bot-Api-Secret-Token": _SECRET},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_healthz_is_unauthenticated(test_app):
    resp = await test_app.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 3: Run to confirm RED**

```bash
docker compose run --rm bot pytest tests/unit/test_webhook_auth.py -v
```

Expected: `ImportError` — `wallet_bot.main` has no `app` or `get_client` yet.

---

### Task 9: Implement `main.py`

**Files:**
- Modify: `src/wallet_bot/main.py`

- [ ] **Step 1: Write the implementation**

```python
"""FastAPI application — webhook handler and DI wiring."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator

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


@app.post("/telegram/webhook", status_code=200)
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
    client: TelegramClientProtocol = Depends(get_client),
) -> dict[str, str]:
    if x_telegram_bot_api_secret_token != settings.webhook_secret.get_secret_value():
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

    # Strip @botname suffix so `/start@walletbot` matches `/start`.
    cmd = msg.text.split("@")[0] if msg.text else None
    if cmd == "/start":
        await handle_start(update, client)
    elif cmd == "/help":
        await handle_help(update, client)
    elif msg.photo:
        await handle_photo(update, client)

    return {"ok": "true"}
```

- [ ] **Step 2: Run tests to confirm GREEN**

```bash
docker compose run --rm bot pytest tests/unit/test_webhook_auth.py tests/unit/test_handlers.py tests/unit/test_config.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Also confirm old smoke test still passes**

```bash
docker compose run --rm bot pytest -v
```

Expected: all tests PASS (smoke test will now fail since `healthz()` moved — update it or delete it; see Step 4).

- [ ] **Step 4: Update `tests/unit/test_smoke.py` to use the new app**

```python
"""Smoke test — verifies the app starts and healthz responds."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_healthz_function_returns_ok():
    from wallet_bot.main import healthz
    result = await healthz()
    assert result == {"status": "ok"}
```

- [ ] **Step 5: Run full suite**

```bash
docker compose run --rm bot pytest -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/wallet_bot/main.py tests/unit/test_webhook_auth.py tests/unit/test_smoke.py tests/conftest.py
git commit -m "feat: add FastAPI app with webhook route, secret auth, and whitelist"
```

---

## Chunk 6: Dockerfile + environment

### Task 10: Update Dockerfile to multi-stage (dev + prod)

**Files:**
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Replace `Dockerfile` with multi-stage build**

```dockerfile
# ── builder: install runtime deps only ──────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --upgrade pip && pip install .

# ── dev: add dev deps + bind-mount friendly ──────────────────────────────────
FROM python:3.12-slim AS dev

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps placeholder (Phase 3 appends barcode libs here).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --upgrade pip && pip install -e '.[dev]'

ENV PORT=8080
EXPOSE 8080
CMD ["bash"]

# ── prod: lean runtime image for Cloud Run ───────────────────────────────────
FROM python:3.12-slim AS prod

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=builder /usr/local /usr/local
COPY src/ ./src/

ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "wallet_bot.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
```

- [ ] **Step 2: Update `docker-compose.yml` to target the `dev` stage**

```yaml
services:
  bot:
    build:
      context: .
      target: dev
    image: wallet-bot:dev
    working_dir: /app
    volumes:
      - ./src:/app/src
      - ./tests:/app/tests
      - ./pyproject.toml:/app/pyproject.toml
    environment:
      - PYTHONPATH=/app/src
    stdin_open: true
    tty: true
    command: bash
```

- [ ] **Step 3: Rebuild and verify tests still pass**

```bash
docker compose build
docker compose run --rm bot pytest -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "chore: multi-stage Dockerfile (dev + prod targets)"
```

---

### Task 11: Update `.env.example`

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Update to match actual Settings field names**

```dotenv
# Telegram — required
BOT_TOKEN=                        # from @BotFather
WEBHOOK_SECRET=                   # random string, set when registering webhook
ALLOWED_TG_USER_IDS=              # comma-separated Telegram user IDs, e.g. 12345,67890

# Anthropic (Phase 2)
ANTHROPIC_API_KEY=

# Google Wallet (Phase 4)
WALLET_ISSUER_ID=
WALLET_CLASS_ID=
# In prod: WALLET_SA_KEY_JSON is mounted from Secret Manager.
# Locally: path to a downloaded service-account JSON file.
WALLET_SA_KEY_PATH=

# Runtime
PORT=8080
LOG_LEVEL=INFO
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: update .env.example to match Settings field names"
```

---

## Chunk 7: Coverage check + lint

### Task 12: Run coverage and lint

- [ ] **Step 1: Run full test suite with coverage**

```bash
docker compose run --rm bot pytest --cov=wallet_bot --cov-report=term-missing -v
```

Expected: all tests PASS; all new `wallet_bot` modules at 100% or near-100% coverage. Fix any gaps before proceeding.

- [ ] **Step 2: Run ruff lint**

```bash
docker compose run --rm bot ruff check src/ tests/
```

Expected: no issues. Fix any that appear.

- [ ] **Step 3: Run ruff format check**

```bash
docker compose run --rm bot ruff format --check src/ tests/
```

Expected: no issues. If there are formatting differences:
```bash
docker compose run --rm bot ruff format src/ tests/
git add -p  # review formatting changes
git commit -m "chore: apply ruff formatting"
```

---

## Chunk 8: Project skills

### Task 13: Create `deploy-cloud-run` skill

- [ ] **Step 1: Invoke the writing-skills workflow**

```
/superpowers:writing-skills
```

Skill name: `deploy-cloud-run`  
Skill description: "Use when deploying the wallet-bot service to Google Cloud Run manually."

The skill should guide through:
1. Verify Docker and gcloud CLI are authenticated
2. Build production image: `docker build --target prod -t me-west1-docker.pkg.dev/PROJECT/wallet-bot/wallet-bot:latest .`
3. Push: `docker push me-west1-docker.pkg.dev/PROJECT/wallet-bot/wallet-bot:latest`
4. Deploy: `gcloud run deploy wallet-bot --image ... --region me-west1 --allow-unauthenticated --service-account wallet-bot-sa@PROJECT.iam.gserviceaccount.com --memory 512Mi --set-secrets BOT_TOKEN=wallet-bot-token:latest,WEBHOOK_SECRET=wallet-bot-webhook-secret:latest,ALLOWED_TG_USER_IDS=wallet-bot-allowed-ids:latest`
5. Verify: `curl https://SERVICE_URL/healthz`

Pre-requisites section (first-time setup):
- Create Artifact Registry repo: `gcloud artifacts repositories create wallet-bot --repository-format=docker --location=me-west1`
- Create service account: `gcloud iam service-accounts create wallet-bot-sa --display-name "Wallet Bot"`
- Grant Secret Manager access: `gcloud projects add-iam-policy-binding PROJECT --member serviceAccount:wallet-bot-sa@PROJECT.iam.gserviceaccount.com --role roles/secretmanager.secretAccessor`
- Create secrets: `gcloud secrets create wallet-bot-token --data-file=-` (pipe token value)

---

### Task 14: Create `tg-webhook-register` skill

- [ ] **Step 1: Invoke the writing-skills workflow**

```
/superpowers:writing-skills
```

Skill name: `tg-webhook-register`  
Skill description: "Use when registering or updating the Telegram webhook URL for the bot."

The skill should guide through:
1. Get the Cloud Run service URL: `gcloud run services describe wallet-bot --region me-west1 --format 'value(status.url)'`
2. Register webhook:
   ```bash
   curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
     -H "Content-Type: application/json" \
     -d "{\"url\": \"${SERVICE_URL}/telegram/webhook\", \"secret_token\": \"${WEBHOOK_SECRET}\"}"
   ```
3. Confirm registration:
   ```bash
   curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
   ```
   Check: `url` matches, `last_error_message` is absent or empty.

---

## Chunk 9: Phase docs + final validation

### Task 15: Update phase docs

**Files:**
- Modify: `phases/01-telegram-webhook/plan.md`
- Modify: `phases/01-telegram-webhook/CLAUDE.md`

- [ ] **Step 1: Fill in `phases/01-telegram-webhook/plan.md`**

```markdown
# Phase 01 — Telegram webhook skeleton

**Full implementation plan:** [docs/superpowers/plans/2026-04-21-phase-01-telegram-webhook.md](../../docs/superpowers/plans/2026-04-21-phase-01-telegram-webhook.md)
**Design spec:** [docs/superpowers/specs/2026-04-21-phase-01-telegram-webhook-design.md](../../docs/superpowers/specs/2026-04-21-phase-01-telegram-webhook-design.md)

## Superpowers checklist
- [x] `/superpowers:brainstorming` — design
- [x] `/superpowers:writing-plans` — detailed plan
- [ ] `/superpowers:test-driven-development` — implementation
- [ ] `/superpowers:verification-before-completion` — pre-PR checks
- [ ] `/ship` — PR + review

## Deploy checklist (manual this phase)
- [ ] `deploy-cloud-run` skill executed — bot live on Cloud Run `me-west1`
- [ ] `tg-webhook-register` skill executed — webhook registered
- [ ] `getWebhookInfo` confirms URL and no errors
- [ ] `/start` from whitelisted Telegram account → reply received
```

- [ ] **Step 2: Fill in `phases/01-telegram-webhook/CLAUDE.md`**

```markdown
# Phase 01 — Notes

## Library choices
- **Web framework:** FastAPI 0.115+ (single-endpoint webhook server)
- **Telegram library:** python-telegram-bot v21 (PTB) — used only for `Bot` client and `Update.de_json()` parsing; no PTB `Application` or dispatcher
- **Config:** pydantic-settings v2 `BaseSettings` — field names must match env var names exactly (pydantic uppercases field names: `bot_token` → `BOT_TOKEN`)
- **Testing:** pytest-asyncio + httpx `AsyncClient` + `asgi-lifespan.LifespanManager`

## Gotchas
- `Update.de_json(body, bot)` requires a `Bot` instance (stored on `app.state.bot` from lifespan). We pass `None` in handler unit tests since Phase 01 handlers don't use bot-context features. Fix in Phase 02 when needed.
- `get_settings()` uses `@lru_cache` — always call `get_settings.cache_clear()` in test fixtures that monkeypatch env vars, or the cache returns stale values.
- `dependency_overrides` only affects FastAPI route injection — the lifespan calls `get_settings()` directly (not via Depends). Use `test_env` fixture + monkeypatch to control both.
- PTB `Bot(token=...)` doesn't validate token format on construction — any string works for unit tests.
- Cloud Run health check uses `GET /healthz` — must return 200 without auth.
```

- [ ] **Step 3: Commit**

```bash
git add phases/01-telegram-webhook/plan.md phases/01-telegram-webhook/CLAUDE.md
git commit -m "docs: fill in Phase 01 plan.md and CLAUDE.md"
```

---

### Task 16: Update `STATUS.md`

**Files:**
- Modify: `STATUS.md`

> Do this step only after the Cloud Run deploy and Telegram webhook smoke test both pass (Tasks 13–14 executed manually).

- [ ] **Step 1: Update STATUS.md**

Update the phase table and current focus:

```markdown
| 01 | Telegram webhook | ✅ done |
```

Change "Current Focus" to:
```markdown
**Phase 02 — Vision extraction** (starts in next session with `/superpowers:brainstorming`).
```

Add a Phase 01 section:
```markdown
## Phase 01 — Telegram webhook ✅

| Task | Status |
|------|--------|
| FastAPI app + `/telegram/webhook` route | ✅ |
| Webhook secret auth (403 on bad/missing token) | ✅ |
| Whitelist check (403 for unknown users) | ✅ |
| `/start`, `/help`, photo ack handlers | ✅ |
| Config via pydantic-settings (fail-fast at boot) | ✅ |
| Multi-stage Dockerfile (dev + prod) | ✅ |
| `deploy-cloud-run` skill | ✅ |
| `tg-webhook-register` skill | ✅ |
| First Cloud Run deploy (`me-west1`) | ✅ |
| Webhook registered + smoke-tested | ✅ |
```

- [ ] **Step 2: Commit**

```bash
git add STATUS.md
git commit -m "docs: mark Phase 01 complete in STATUS.md"
```

---

### Task 17: Ship

- [ ] **Step 1: Run the full pre-ship validation**

```bash
docker compose run --rm bot pytest --cov=wallet_bot --cov-report=term-missing -v
docker compose run --rm bot ruff check src/ tests/
docker compose run --rm bot ruff format --check src/ tests/
```

All must pass with zero errors before proceeding.

- [ ] **Step 2: Invoke `/ship`**

```
/ship
```

The ship command runs tests + lint + audit, opens the PR, and dispatches the reviewer agent.
