# STATUS.md — Progress Tracker

Last updated: 2026-04-29 — Phase 04 merged ✅ (PR #5). Next focus: Phase 03 revision (pyzbar barcode decoding).

## Current Focus

**Phase 03 revision — replace Gemini barcode extraction with `pyzbar`** — ⬜ not started. Start with `/superpowers:brainstorming` in a new session.

---

## Phase status

| # | Phase | Status |
|---|---|---|
| 00 | Scaffold | ✅ done |
| 01 | Telegram webhook | ✅ done |
| 02 | Vision extraction | ✅ done |
| 03 | Barcode decoding | ✅ done |
| 04 | Google Wallet pass | ✅ done |
| 05 | End-to-end flow | ⬜ not started |
| 06 | Observability & hardening | ⬜ not started |
| 07 | Release pipeline | ⬜ not started |

Legend: ✅ done · 🔄 in progress · ⬜ not started

---

## Phase 04 — Google Wallet pass ✅

| Task | Status |
|------|--------|
| `google-auth` + `google-auth-httplib2` dependencies | ✅ |
| `models/wallet.py` — `WalletObject`, `PassBundle` | ✅ |
| `config.py` — `wallet_issuer_id`, `wallet_sa_json`, `wallet_origins` | ✅ |
| `models/callback_ids.py` — `WALLET_GET_LINK`, `WALLET_BUNDLE_YES`, `WALLET_BUNDLE_NO` | ✅ |
| `services/pass_store.py` — in-memory per-chat bundle tracker | ✅ |
| `services/wallet_service.py` — object builder + RS256 JWT signer | ✅ |
| `services/telegram_client.py` — `send_url_button` | ✅ |
| `handlers/callback_handler.py` — full multi-ticket bundle flow | ✅ |
| `handlers/start_handler.py` + `help_handler.py` — multi-ticket UX explained | ✅ |
| `main.py` — `PassStore` + `WalletService` wired via FastAPI DI | ✅ |
| 175 tests green, ruff lint clean | ✅ |
| JWT structure validated by `wallet-jwt-validator` agent | ✅ |
| PR opened + merged | ✅ |
| `wallet-pass-preview` skill created via `/superpowers:writing-skills` | ⬜ deferred |

## Phase 03 — Barcode decoding ✅ (revision pending)

| Task | Status |
|------|--------|
| `BarcodeResult` model + `ExtractedTicket.barcode` field | ✅ |
| `barcode_value` excluded from approve log | ✅ |
| `STRUCTURED_PROMPT` extended with barcode instruction | ✅ |
| Photo handler tests cover barcode presence/absence | ✅ |
| Design doc + `phases/03-barcode-decode/plan.md` updated | ✅ |
| `STATUS.md` updated, current focus → Phase 04 | ✅ |
| PR #4 merged to main | ✅ |
| **Revision needed:** replace Gemini barcode extraction with `pyzbar` | ⬜ |

> **Why:** E2E testing showed Gemini reads QR code values inaccurately (visual OCR on binary pixel matrix). `pyzbar` decodes the exact binary payload reliably. Gemini should own human-readable text fields only; `pyzbar` should own `barcode_value` + `barcode_type`. Remove barcode instructions from the Gemini prompt.

## Phase 02 — Vision extraction ✅

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
| Unit coverage ≥80% (118 tests green, 92% total) | ✅ |
| Manual end-to-end test via ngrok + real bot (photo → edit → approve, "typing…" + "✓ updated" both visible) | ✅ |
| Multi-ticket-per-event design notes added to phases 04 + 05 | ✅ |
| `phases/02-vision-extraction/plan.md` — superseded with executed plan summary | ✅ |
| `.env.example` — `GEMINI_API_KEY` + `GEMINI_MODEL` documented | ✅ |
| Post-review fixes: non-private callback acks the query; `GeminiSettings` keeps env access in `config.py` | ✅ |
| Live integration test (`pytest -m integration` with real key) | ⬜ deferred — eval script + manual e2e cover this |
| PR #3 merged to main | ✅ |

## Phase 01 — Telegram webhook ✅

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
| Cloud Run deploy (me-west1) | → deferred to Phase 07 |
| `deploy-cloud-run` skill (via `/superpowers:writing-skills`) | → deferred to Phase 07 |
| `tg-webhook-register` skill (via `/superpowers:writing-skills`) | → deferred to Phase 07 |
| PR opened, CI green, merged to main | ✅ |

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
| `.claude/commands/release.md` + `RELEASING.md` | → deferred to Phase 07 |
| `.claude/agents/{reviewer,secret-scanner,wallet-jwt-validator}.md` | ✅ |
| `.claude/skills/*` | ⬜ deferred — each skill created via `/superpowers:writing-skills` in the phase that needs it |
| PR opened, CI green, merged to main | ✅ |
