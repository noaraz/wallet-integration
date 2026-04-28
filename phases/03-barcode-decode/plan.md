# Phase 03 — Barcode decoding ✅

> Executed. Design doc at
> `docs/superpowers/specs/2026-04-28-phase-03-barcode-decoding-design.md`.

## What this phase delivers

Gemini's existing vision call is extended to also decode any QR code or barcode
visible in the ticket photo. The payload is stored as a nullable `BarcodeResult`
nested on `ExtractedTicket`. Phase 04 reads `ticket.barcode.barcode_type` and
`ticket.barcode.barcode_value` when building the Google Wallet pass.

## Decisions

- **No barcode library.** Target tickets are Israeli concert/sports QR codes
  with text/URL payloads. Gemini Vision reads these directly — zero new native
  deps, zero Docker changes.
- **Nested `BarcodeResult` model** (not flat fields) so Phase 04 gets a clean
  `ticket.barcode` interface. Field names `barcode_type` / `barcode_value`
  avoid shadowing `builtins.type` and are `mypy --strict`-friendly (Phase 07).
- **Empty-string normalisation.** A `field_validator` converts `""` →
  `None` so Phase 04 always receives `None` or a meaningful string.
- **Silent fallback** when `barcode` is `None`. No user-facing warning in
  Phase 03; Phase 04 decides whether a barcode is required.
- **`barcode_value` excluded from INFO logs** (may be a signed token or
  PII-adjacent). `barcode_type` is safe metadata and stays in the log.

## What landed

| Component | Notes |
|---|---|
| `models/ticket.py` | `BarcodeResult` (barcode_type, barcode_value + empty→None validator); `ExtractedTicket.barcode: BarcodeResult \| None` |
| `services/gemini_vision.py` | `STRUCTURED_PROMPT` extended with barcode instruction |
| `handlers/callback_handler.py` | `model_dump(exclude={"raw_text": True, "barcode": {"barcode_value"}})` |

## Coverage

All existing 118 tests still pass. 16 new tests added across `test_ticket.py`,
`test_gemini_vision.py`, `test_callback_handler.py`, `test_photo_handler.py`.
Total: 134 tests green.

## Superpowers checklist

- [x] `/superpowers:brainstorming`
- [x] `/superpowers:writing-plans`
- [x] `/superpowers:test-driven-development`
- [ ] `/ship`
