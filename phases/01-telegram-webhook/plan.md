# Phase 01 — Telegram webhook skeleton

Design spec: `docs/superpowers/specs/2026-04-21-phase-01-telegram-webhook-design.md`
Implementation plan: `docs/superpowers/plans/2026-04-21-phase-01-telegram-webhook.md`

## Scope

- `POST /telegram/webhook` verifying `X-Telegram-Bot-Api-Secret-Token` (→ 403 if absent or wrong).
- Whitelist check against `ALLOWED_TG_USER_IDS` (→ 403 if user not in list).
- `/start`, `/help` commands; photo message → "Got it, processing…" reply.
- `/healthz` unauthenticated liveness probe.
- First Cloud Run deploy (me-west1) → stable HTTPS URL → webhook registered with Telegram.
- Project skills: `deploy-cloud-run`, `tg-webhook-register` (created via `/superpowers:writing-skills`).

## Technology choices

| Concern | Choice | Rationale |
|---|---|---|
| Web framework | FastAPI + uvicorn | Async-first, fast startup, clean DI |
| Telegram library | python-telegram-bot v21 (thin PTB) | `Update.de_json` + `Bot` client only — no PTB dispatcher |
| Settings | pydantic-settings v2 `BaseSettings` | Env-first, Secret Manager-ready; `SecretStr` for tokens |
| Testing | pytest-asyncio auto mode + httpx ASGITransport | Full ASGI stack without live server |
| Cloud | Cloud Run (me-west1), multi-stage Dockerfile | Serverless, no infra to manage |

## Key design decisions

- **Thin PTB**: use only `Bot` (for `send_message`) and `Update.de_json` (for parsing). No PTB Application/dispatcher — FastAPI owns the request lifecycle.
- **`TelegramClientProtocol`**: `Protocol` interface injected into handlers; `TelegramClient` is the prod impl; `FakeClient` used in tests.
- **Comma-separated whitelist**: `_EnvWithCommaIds` subclasses `EnvSettingsSource` to intercept `ALLOWED_TG_USER_IDS` before pydantic-settings attempts JSON-decode.
- **Command stripping**: `parts = msg.text.split(); cmd = parts[0].split("@")[0] if parts else None` — correctly strips `@botname` from command token only.
- **Multi-stage Dockerfile**: `base` → `dev` (editable + dev extras) / `prod` (non-editable, uvicorn CMD).

## Superpowers checklist

- [x] `/superpowers:brainstorming` — design
- [x] `/superpowers:writing-plans` — detailed plan
- [x] `/superpowers:test-driven-development` — implementation
- [ ] `/superpowers:verification-before-completion` — pre-PR checks
- [ ] `deploy-cloud-run` skill + Cloud Run deploy
- [ ] `tg-webhook-register` skill + webhook registration
- [ ] `/ship` — PR + review
