# Phase 02 — Vision extraction (Gemini-only, interactive edit) ✅

> Executed. Plan-of-record summary; the live brainstorm/plan documents
> are at `~/.claude/plans/phase-02-starry-wadler.md` and
> `docs/research/2026-04-22-hebrew-ocr-library-survey.md`.

## What this phase delivers

A user DMs the bot a ticket photo → bot replies within ~10 s with an
editable draft (every field plus an inline keyboard) → user fixes any
wrong field with tap-and-reply → user taps Approve → bot logs the
structured ticket and confirms.

No wallet pass yet (Phase 04). No barcode (Phase 03).

## Decisions

- **Gemini 2.5 Flash** (overridable via `GEMINI_MODEL`) won the OCR
  eval decisively on Hebrew tickets. No fallback OCR engine; no
  confidence-based model switching. Failures fall back to a generic
  "please try again" reply, not partial data.
- **Single-draft-per-chat** in-memory `DraftStore` with 1 h TTL and
  32-entry LRU cap. Multi-ticket-per-event handling lives in Phase 04
  (`eventTicketClass` + N objects, deterministic class id) and
  Phase 05 (UX choice).
- **Layered architecture** (per `CLAUDE.md`): models → services →
  handlers. Vision is reached only through the
  `wallet_bot.services.vision_service` facade so Phase 02's choice of
  backend stays swappable.

## What landed

| Component | Notes |
|---|---|
| `models/ticket.py` | `ExtractedTicket` (10 optional fields + `raw_text`), `DraftState` |
| `models/callback_ids.py` | `CallbackId` StrEnum + strict `parse_callback_id` (rejects `edit_../../secret`, case variants, `edit_raw_text`) |
| `services/draft_store.py` | per-chat asyncio.Lock, TTL eviction on access, LRU cap |
| `services/vision_service.py` | `VisionServiceProtocol` + `TextDumpProtocol` + `VisionExtractionError`; the swap seam |
| `services/gemini_vision.py` | google-genai backend; SDK errors wrapped to never leak keys/tracebacks |
| `services/telegram_client.py` | `send_with_inline_keyboard`, `edit_message_text`, `answer_callback_query`, `send_force_reply`, `download_photo_bytes`, `send_chat_action` |
| `handlers/_safe.py` | `@safe_handler` decorator → `logger.exception` + generic user reply |
| `handlers/_render.py` | Single source of truth for draft layout (10 fields, Approve/Cancel last) |
| `handlers/_typing.py` | `typing_indicator` async-CM that re-fires every 4 s during long ops |
| `handlers/photo_handler.py` | download → typing-loop wrapping vision.extract → keyboard |
| `handlers/callback_handler.py` | answer query → EDIT_* (force-reply, set editing_field) / APPROVE (log + clear) / CANCEL |
| `handlers/edit_reply_handler.py` | apply edit → re-render in place → "✓ \<Label\> updated." inline ack |
| `main.py` | webhook routing: photo / callback / text-in-edit / DM-only; lazy vision-service init |
| `config.py` | `GEMINI_API_KEY` (required) + `GEMINI_MODEL` (default `gemini-2.5-flash`, override to ride out outages) |
| `scripts/eval_ocr.py` + `debugging-hebrew-ocr` skill | Re-use the same facade |

## Security invariants (verified by tests)

- Approved log line excludes `raw_text` (`model_dump(exclude={"raw_text"})`)
- Unknown / malformed `callback_data` is dropped silently with no draft mutation
- Group-chat messages get a one-shot "DM only" reply, no downstream handler invoked
- `VisionExtractionError` surface text is generic — SDK error messages never reach the user
- All outbound text uses `parse_mode=None` (no Markdown/HTML interpretation of OCR content)
- Webhook secret comparison via `hmac.compare_digest`

## Coverage

115 unit tests, ruff clean, end-to-end manually verified via ngrok +
real Telegram bot (photo extracted in 8-10 s, edit confirmation
visible, approve logs JSON without `raw_text`).

## Cloud Run note

In-memory `DraftStore` means `--min-instances=1` is required to avoid
draft loss between a photo and its follow-up edit. Fits the free tier
at `cpu=1, memory=512Mi`.

## Out of scope (for future phases)

- Barcode decoding (Phase 03)
- Wallet pass + JWT (Phase 04 — also where multi-ticket-per-event lives)
- End-to-end UX polish + multi-ticket UX (Phase 05)
- Persistent draft storage (Phase 05+ if needed)
- Structured-logging cost monitoring (Phase 06)

## Superpowers checklist

- [x] `/superpowers:brainstorming`
- [x] `/superpowers:writing-plans`
- [x] `/superpowers:test-driven-development`
- [ ] `/ship`
