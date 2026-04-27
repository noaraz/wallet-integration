# STATUS.md — Progress Tracker

Last updated: 2026-04-27 — Phase 02 verified end-to-end on real Telegram, pending `.env.example` manual edit + PR

## Current Focus

**Phase 02 — Vision extraction (Gemini-only, interactive edit)** — 115 unit tests green, ruff clean, manually verified via ngrok + real bot (photo → 10 s OCR with refreshing "typing…" → editable draft → "✓ updated" inline ack on edit → approve logs structured JSON without `raw_text`). Pending: `.env.example` manual edit (pre-edit guard), then `/ship`.

---

## Phase status

| # | Phase | Status |
|---|---|---|
| 00 | Scaffold | ✅ done |
| 01 | Telegram webhook | 🔄 in PR |
| 02 | Vision extraction | 🔄 in PR |
| 03 | Barcode decoding | ⬜ not started |
| 04 | Google Wallet pass | ⬜ not started |
| 05 | End-to-end flow | ⬜ not started |
| 06 | Observability & hardening | ⬜ not started |
| 07 | Release pipeline | ⬜ not started |

Legend: ✅ done · 🔄 in progress · ⬜ not started

---

## Phase 02 — Vision extraction 🔄

| Task | Status |
|------|--------|
| OCR engine eval (Gemini won decisively on Hebrew) | ✅ |
| `models/ticket.py` — `ExtractedTicket`, `DraftState` | ✅ |
| `models/callback_ids.py` — `CallbackId` enum + strict parser | ✅ |
| `services/draft_store.py` — in-memory, per-chat lock, TTL, LRU | ✅ |
| `services/vision_service.py` — facade (`VisionServiceProtocol`, `TextDumpProtocol`, `VisionExtractionError`) | ✅ |
| `services/gemini_vision.py` — shared Gemini backend (script + skill + bot) | ✅ |
| `services/telegram_client.py` — `send_with_inline_keyboard`, `edit_message_text`, `answer_callback_query`, `send_force_reply`, `download_photo_bytes`, `send_chat_action` | ✅ |
| `handlers/_safe.py` + `handlers/_render.py` + `handlers/_typing.py` | ✅ |
| `handlers/photo_handler.py` — download → extract → render draft, with refreshing "typing…" indicator | ✅ |
| `handlers/callback_handler.py` — edit / approve / cancel (no redundant message-edit on EDIT_* tap) | ✅ |
| `handlers/edit_reply_handler.py` — apply edit → re-render in place → inline "✓ updated" ack | ✅ |
| `main.py` — callback_query + text-in-edit-mode + DM-only routing + INFO logging | ✅ |
| `config.py` — `GEMINI_API_KEY` (required) + `GEMINI_MODEL` (override default model) | ✅ |
| `pyproject.toml` — `google-genai` promoted to main deps | ✅ |
| `scripts/eval_ocr.py` + `debugging-hebrew-ocr` skill re-use facade | ✅ |
| Unit coverage ≥80% (115 tests green) | ✅ |
| Manual end-to-end test via ngrok + real bot (photo → edit → approve, "typing…" + "✓ updated" both visible) | ✅ |
| Multi-ticket-per-event design notes added to phases 04 + 05 | ✅ |
| `phases/02-vision-extraction/plan.md` — superseded with executed plan summary | ✅ |
| `.env.example` — add `GEMINI_API_KEY=` and `GEMINI_MODEL=` (manual edit; pre-edit guard) | ⬜ |
| Live integration test (`pytest -m integration` with real key) | ⬜ deferred — eval script + manual e2e cover this |
| PR opened, CI green, merged to main | ⬜ |

## Phase 01 — Telegram webhook 🔄

| Task | Status |
|------|--------|
| FastAPI app skeleton (`main.py`, lifespan, DI) | ✅ |
| `config.py` — pydantic-settings, SecretStr, comma-separated whitelist | ✅ |
| `services/telegram_client.py` — Protocol + TelegramClient | ✅ |
| `/start`, `/help`, photo handlers | ✅ |
| Webhook auth + whitelist tests | ✅ |
| Multi-stage Dockerfile (dev / prod targets) | ✅ |
| `.env.example` updated to match real env var names | ✅ |
| Coverage ≥80% (actual: 90%), lint clean | ✅ |
| `phases/01-*/plan.md` + `CLAUDE.md` filled in | ✅ |
| Cloud Run deploy (me-west1) | ⬜ |
| `deploy-cloud-run` skill (via `/superpowers:writing-skills`) | ⬜ |
| `tg-webhook-register` skill (via `/superpowers:writing-skills`) | ⬜ |
| PR opened, CI green, merged to main | ⬜ |

## Phase 00 — Scaffold ✅

| Task | Status |
|------|--------|
| Baseline commit on main + branch protection | ✅ |
| Root markdowns (CLAUDE, PLAN, STATUS, README) | ✅ |
| Layered source layout (`src/wallet_bot/{models,services,handlers}/`) | ✅ |
| pyproject.toml, Dockerfile, .dockerignore, .env.example | ✅ |
| Phase folders (00–07) with plan.md + CLAUDE.md | ✅ |
| Hooks (pre_edit_guard, post_python_edit, start) | ✅ |
| `.claude/commands/{ship,new-phase}.md` | ✅ |
| `.claude/commands/release.md` + `RELEASING.md` | ⬜ deferred to Phase 07 |
| `.claude/agents/{reviewer,secret-scanner,wallet-jwt-validator}.md` | ✅ |
| `.claude/skills/*` | ⬜ deferred — each skill created via `/superpowers:writing-skills` in the phase that needs it |
| PR opened, CI green, merged to main | ✅ |
