# Phase 01 — Telegram Webhook Skeleton: Design Spec

**Date:** 2026-04-21  
**Phase:** 01 — Telegram webhook skeleton  
**Branch:** `feat/phase-01-telegram-webhook`  
**Status:** Approved — ready for implementation planning

---

## Overview

Stand up a FastAPI webhook server that receives Telegram updates, verifies authenticity, enforces a user whitelist, and responds to `/start`, `/help`, and photo messages. Deploy to Cloud Run (`me-west1`) as the first live instance of the bot.

---

## Technology choices

| Concern | Choice | Rationale |
|---|---|---|
| Web framework | FastAPI | Async-first, de-facto standard, free `/healthz`, minimal overhead for a single-route server |
| Telegram library | python-telegram-bot v21 (PTB) | Stable, well-documented, `Bot` client + `Update` model cover all phases without framework lock-in |
| GCP region | `me-west1` (Tel Aviv) | Lowest latency for primary user location |
| Config | pydantic-settings `BaseSettings` | Env-var parsing, `SecretStr` masking, fail-fast validation at startup |
| Testing | pytest-asyncio + httpx + asgi-lifespan | Async route tests with lifespan events firing; no extra Telegram-specific test library |

---

## Architecture

### Layered architecture (SOLID + DI)

```
src/wallet_bot/
├── main.py          # FastAPI app, lifespan, DI wiring, routes
├── config.py        # pydantic-settings BaseSettings
├── models/          # Pure domain data — no I/O, no framework types
├── services/        # External integrations (Telegram Bot client)
└── handlers/        # One async function per Telegram update type
```

**Layer rules:**

| Layer | Knows about | Does NOT know about |
|---|---|---|
| `models/` | Python types only | Telegram, HTTP, anything external |
| `services/` | External APIs, models | Telegram update shape, handlers |
| `handlers/` | Models, services (via protocol) | FastAPI internals, HTTP details |
| `main.py` | FastAPI routes, handlers, DI wiring | Handler/service internals |

### Request flow

```
POST /telegram/webhook
  │
  ├─ 1. Verify X-Telegram-Bot-Api-Secret-Token → 403 if absent or wrong
  ├─ 2. Parse body → Update.de_json()
  ├─ 3. Whitelist check on update.effective_user.id → 403 if not in list
  └─ 4. Dispatch by update type:
         /start   → handlers/start_handler.py
         /help    → handlers/help_handler.py
         photo    → handlers/photo_handler.py
         other   → 200 (silent ignore)
```

`GET /healthz` — unauthenticated, returns `{"status": "ok"}`, used by Cloud Run health checks.

---

## Config & secrets

```python
class Settings(BaseSettings):
    bot_token: SecretStr           # env var: BOT_TOKEN
    webhook_secret: SecretStr      # env var: WEBHOOK_SECRET
    allowed_tg_user_ids: list[int] # env var: ALLOWED_TG_USER_IDS=123,456

    model_config = SettingsConfigDict(env_file=".env")

    @field_validator("allowed_tg_user_ids", mode="before")
    @classmethod
    def parse_ids(cls, v: str | list) -> list[int]:
        if isinstance(v, str):
            ids = [int(x.strip()) for x in v.split(",") if x.strip()]
            if not ids:
                raise ValueError("ALLOWED_TG_USER_IDS must not be empty")
            return ids
        return v
```

Field names are lowercase snake_case; pydantic-settings uppercases them to derive env var names (`bot_token` → `BOT_TOKEN`, `webhook_secret` → `WEBHOOK_SECRET`, `allowed_tg_user_ids` → `ALLOWED_TG_USER_IDS`).

- `get_settings()` cached with `@lru_cache`
- Injected via FastAPI `Depends(get_settings)` — never via `app.state`
- Called eagerly in the `lifespan` startup handler so missing vars fail at boot, not mid-request
- In prod: secrets live in Secret Manager, mounted as env vars by Cloud Run (no client library needed)

**Security notes:**
- `SecretStr` prevents tokens appearing in logs or `repr()`
- Empty whitelist is a `ValidationError` — misconfiguration fails loudly
- `403` for both absent and wrong secret token (one code path, no ambiguity)

---

## Handlers

Each handler is a plain async function:

```python
async def handle_start(update: Update, client: TelegramClientProtocol) -> None: ...
async def handle_help(update: Update, client: TelegramClientProtocol) -> None: ...
async def handle_photo(update: Update, client: TelegramClientProtocol) -> None: ...
```

- No FastAPI dependency — testable with a `FakeClient`
- `TelegramClientProtocol` defined in `services/telegram_client.py`; concrete `TelegramClient` wraps `ptb.Bot`

**Reply content (Phase 01 placeholders):**

| Handler | Reply text |
|---|---|
| `/start` | Welcome message + brief description of the bot |
| `/help` | List of supported commands |
| photo | "Got it, processing…" |

---

## Services

**`services/telegram_client.py`**

```python
class TelegramClientProtocol(Protocol):
    async def send_text(self, chat_id: int, text: str) -> None: ...

class TelegramClient:
    def __init__(self, bot: Bot) -> None: ...
    async def send_text(self, chat_id: int, text: str) -> None: ...
```

`Bot` is constructed once at startup (in `lifespan`) and injected into `TelegramClient`. `TelegramClient` is injected into handlers via `Depends`.

---

## Testing strategy

**Dev deps added:** `httpx`, `asgi-lifespan`  
**`pyproject.toml` setting:** `asyncio_default_fixture_loop_scope = "function"`

### `tests/unit/test_webhook_auth.py`

Uses `httpx.AsyncClient` + `asgi-lifespan.LifespanManager` (so startup validation runs):

- Missing `X-Telegram-Bot-Api-Secret-Token` → 403
- Wrong token value → 403
- Correct token + non-whitelisted user ID → 403
- Correct token + whitelisted user + `/start` → 200

### `tests/unit/test_handlers.py`

Pure async unit tests, no HTTP layer:

```python
class FakeClient:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
    async def send_text(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))
```

- `/start` → `FakeClient.sent` contains welcome text for correct `chat_id`
- `/help` → help text sent
- photo → "Got it, processing…" sent

### `tests/unit/test_config.py`

- Missing `BOT_TOKEN` → `ValidationError`
- Missing `WEBHOOK_SECRET` → `ValidationError`
- `ALLOWED_TG_USER_IDS=""` → `ValidationError`
- `ALLOWED_TG_USER_IDS="123,456"` → `[123, 456]`

---

## Dockerfile (production)

Multi-stage build:

```dockerfile
# Build stage — install dependencies
FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Runtime stage — lean image
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=builder /usr/local /usr/local
COPY src/ src/
CMD ["uvicorn", "wallet_bot.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
```

`PORT` env var override: Cloud Run injects `PORT=8080` by default; uvicorn hardcodes 8080 here (same value, no mismatch).

---

## Cloud Run deployment

**`deploy-cloud-run` skill** (created this phase via `/superpowers:writing-skills`) guides through:

1. Create a dedicated GCP service account `wallet-bot-sa`
2. Grant `roles/secretmanager.secretAccessor` on each secret
3. Create secrets in Secret Manager: `wallet-bot-token`, `wallet-bot-webhook-secret`, `wallet-bot-allowed-ids`
4. Build and push image to Artifact Registry, then deploy:
   ```bash
   # Build and push
   docker build -t me-west1-docker.pkg.dev/PROJECT/wallet-bot/wallet-bot:latest .
   docker push me-west1-docker.pkg.dev/PROJECT/wallet-bot/wallet-bot:latest

   # Deploy the pre-built image (uses the multi-stage Dockerfile above)
   gcloud run deploy wallet-bot \
     --image me-west1-docker.pkg.dev/PROJECT/wallet-bot/wallet-bot:latest \
     --region me-west1 \
     --allow-unauthenticated \
     --service-account wallet-bot-sa@PROJECT.iam.gserviceaccount.com \
     --memory 512Mi \
     --set-secrets=BOT_TOKEN=wallet-bot-token:latest,\
   WEBHOOK_SECRET=wallet-bot-webhook-secret:latest,\
   ALLOWED_TG_USER_IDS=wallet-bot-allowed-ids:latest
   ```
   > Note: `--source .` would also work (Cloud Build picks up the Dockerfile) but pre-building gives a reproducible image and faster re-deploys.
5. Verify: `curl https://SERVICE_URL/healthz` → `{"status":"ok"}`

**`tg-webhook-register` skill** guides through:

1. Get the live Cloud Run URL
2. Call `setWebhook`:
   ```
   POST https://api.telegram.org/bot{TOKEN}/setWebhook
     url={SERVICE_URL}/telegram/webhook
     secret_token={WEBHOOK_SECRET}
   ```
3. Confirm with `getWebhookInfo` — check `url` and `pending_update_count`

---

## Phase 01 done criteria

- [ ] All three test suites pass (`docker compose run --rm bot pytest -v`)
- [ ] Coverage run passes (`docker compose run --rm bot pytest --cov=wallet_bot --cov-report=term-missing`) — all new code fully exercised
- [ ] Ruff lint + format clean
- [ ] Bot deployed to Cloud Run `me-west1`
- [ ] Webhook registered and `getWebhookInfo` confirms it
- [ ] Send `/start` from whitelisted Telegram account → reply lands
- [ ] `phases/01-telegram-webhook/plan.md` and `CLAUDE.md` filled in
- [ ] `STATUS.md` updated: Phase 01 ✅, Current Focus → Phase 02
- [ ] PR merged to `main` via `/ship`

---

## Files changed this phase

| File | Action |
|---|---|
| `src/wallet_bot/main.py` | Replace stub with FastAPI app + webhook route |
| `src/wallet_bot/config.py` | Replace stub with pydantic-settings `Settings` |
| `src/wallet_bot/handlers/start_handler.py` | New |
| `src/wallet_bot/handlers/help_handler.py` | New |
| `src/wallet_bot/handlers/photo_handler.py` | New |
| `src/wallet_bot/services/telegram_client.py` | New |
| `src/wallet_bot/viewmodels/` | Delete (renamed to `handlers/`) |
| `src/wallet_bot/views/` | Delete |
| `tests/unit/test_webhook_auth.py` | New |
| `tests/unit/test_handlers.py` | New |
| `tests/unit/test_config.py` | New |
| `pyproject.toml` | Add runtime + dev deps |
| `Dockerfile` | Multi-stage production build |
| `.env.example` | Add three new env var entries |
| `.claude/skills/deploy-cloud-run/SKILL.md` | New (via `/superpowers:writing-skills`) |
| `.claude/skills/tg-webhook-register/SKILL.md` | New (via `/superpowers:writing-skills`) |
| `phases/01-telegram-webhook/plan.md` | Fill in from this spec |
| `phases/01-telegram-webhook/CLAUDE.md` | Fill in gotchas + library choices |
| `STATUS.md` | Update at phase end |
