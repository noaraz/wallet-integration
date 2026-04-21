# Phase 01 — Telegram webhook skeleton

**Placeholder** — brainstorm this phase in a fresh session with `/superpowers:brainstorming`.

## Scope (from root PLAN.md)
- `POST /telegram/webhook` verifying `X-Telegram-Bot-Api-Secret-Token`.
- Whitelist check against `ALLOWED_TG_USER_IDS`.
- `/start`, `/help` commands; on photo: reply "got it, processing…".
- First Cloud Run deploy → stable HTTPS URL → register webhook with Telegram.
- Create project skills via `/superpowers:writing-skills`: `deploy-cloud-run`, `tg-webhook-register`.
- Tests: webhook signature, whitelist rejection, photo ack.

## Superpowers checklist
- [ ] `/superpowers:brainstorming` — design
- [ ] `/superpowers:writing-plans` — detailed plan in this file
- [ ] `/superpowers:test-driven-development` — implementation
- [ ] `/superpowers:verification-before-completion` — pre-PR checks
- [ ] `/ship` — PR + review
