# Phase 03 — Barcode decoding design
_Date: 2026-04-28_

## Context

Phase 02 shipped Hebrew OCR via Gemini Vision: a ticket photo → structured
`ExtractedTicket` (10 text fields) → interactive draft → approve. Phase 04
needs to build a Google Wallet `eventTicketObject`, which has a `barcode.value`
/ `barcode.type` field pair. Phase 03 adds that barcode extraction so Phase 04
has something to put there.

Original plan called for a dedicated Python barcode-decoding library
(pyzbar / zxing-cpp). Decision: skip the library entirely. Target tickets are
Israeli concert/sports event tickets whose barcodes are QR codes encoding
text/URL payloads — Gemini Vision can read those directly from the photo.
Extending the existing Gemini call adds zero latency, zero new native deps, and
zero Docker changes.

---

## Approach — Extend Gemini extraction (Option C: nested model)

Single Gemini call already runs. We extend its JSON schema and prompt to also
extract barcode data, returned as a nullable nested object on `ExtractedTicket`.

---

## Data model (`src/wallet_bot/models/ticket.py`)

Add a `BarcodeResult` model alongside `ExtractedTicket`:

```python
class BarcodeResult(BaseModel):
    barcode_type: str        # "QR_CODE" | "CODE_128" | "AZTEC" | …
    barcode_value: str | None = None  # decoded payload; None if empty/unreadable

    @field_validator("barcode_value")
    @classmethod
    def empty_to_none(cls, v: str | None) -> str | None:
        return None if v == "" else v

class ExtractedTicket(BaseModel):
    # existing 10 fields unchanged …
    barcode: BarcodeResult | None = None
```

- Field names are `barcode_type` / `barcode_value` (avoids shadowing `builtins.type`; cleaner under `mypy --strict` in Phase 07).
- `barcode_value` is `str | None`: Gemini may return an empty string when it spots a symbol but can't decode it — the validator normalises `""` → `None` so Phase 04 always gets `None` or a meaningful string.
- `barcode` is `None` when Gemini omits the field entirely (silent fallback — no user-facing warning in Phase 03; Phase 04 decides if it's required).
- `barcode_value` is added to the `model_dump(exclude=...)` set in the approve log, alongside `raw_text`. Barcode payloads can be signed tokens or PII-adjacent. `barcode_type` remains in the log (it is safe metadata).
- `DraftState` wraps `ExtractedTicket` — no change needed; the optional field with `None` default handles all existing stored objects.
- All existing tests remain green — the new field is optional with a `None` default.

---

## Prompt extension (`src/wallet_bot/services/gemini_vision.py`)

The Gemini SDK infers the JSON schema from `response_schema=ExtractedTicket` (the Pydantic class directly). Adding `barcode: BarcodeResult | None` to `ExtractedTicket` automatically exposes the nested schema to the SDK — no hand-crafted JSON dict needed.

Add one instruction sentence to the extraction prompt:

> "If the ticket contains a QR code, barcode, or any machine-readable symbol,
> set `barcode_type` to the format name (e.g. QR_CODE, CODE_128, AZTEC) and
> `barcode_value` to its decoded payload. If none is visible or readable, omit
> the barcode field entirely."

No changes to `vision_service.py`, its Protocol, or the facade factories.

---

## UX

Silent fallback. When `barcode` is `None`, the draft renders exactly as today —
no extra row, no warning. Phase 04 will determine whether a barcode is required
for a valid wallet pass; we don't block or warn on something Phase 04 hasn't
defined yet.

---

## Files changed

| File | Change |
|---|---|
| `src/wallet_bot/models/ticket.py` | Add `BarcodeResult`; add `barcode: BarcodeResult \| None = None` to `ExtractedTicket` |
| `src/wallet_bot/services/gemini_vision.py` | Extend JSON schema + prompt instruction |
| `src/wallet_bot/handlers/_render.py` | No change required (barcode not rendered in draft) |
| `src/wallet_bot/handlers/callback_handler.py` | Add `barcode` to `model_dump(exclude=...)` in approve log |
| `tests/unit/models/test_ticket.py` | Extend: BarcodeResult validation; ExtractedTicket with/without barcode |
| `tests/unit/services/test_gemini_vision.py` | Extend: barcode present, absent, Gemini returns empty string value |
| `tests/unit/handlers/test_photo_handler.py` | Extend _FakeVision to return tickets with/without barcode |

---

## Testing strategy

No real ticket images in the test suite (PII). All tests use mocked Gemini
responses or fake service doubles — consistent with the existing 118-test suite.

| Test area | Cases |
|---|---|
| `BarcodeResult` model | Valid payload; empty `barcode_value` `""` → normalised to `None` |
| `ExtractedTicket` with barcode | Parses correctly; `barcode_value` excluded from approve log dump; `barcode_type` present in log |
| `ExtractedTicket` without barcode | `barcode` defaults to `None`; no regression on existing tests |
| `GeminiVisionService` | Gemini returns full barcode → parsed; returns `null` barcode → `None`; returns `barcode_value: ""` → `None` via validator |
| `photo_handler` | Draft stored with barcode; draft stored without barcode |

Note: "malformed barcode object" from Gemini is not a distinct test case — `response_schema=ExtractedTicket` means the SDK enforces the schema; a structurally invalid response would raise `VisionExtractionError` (existing behaviour), not silently set `barcode=None`.

Coverage target: ≥80% (current: 92% — maintain or improve).

---

## Verification (end-to-end)

1. `docker compose run --rm bot pytest -v` — all tests green
2. `docker compose run --rm bot ruff check src/ tests/` — lint clean
3. Manual via ngrok + real bot: send a ticket photo with a visible QR code →
   approve → check INFO log contains `barcode.type` and `barcode.value` is
   absent from the log line.
4. Send a photo without a barcode → approve → log line has no `barcode` key.

---

## Documentation to write (part of this phase)

| File | Action |
|---|---|
| `docs/superpowers/specs/2026-04-28-phase-03-barcode-decoding-design.md` | Create — copy of this design doc; commit alongside implementation |
| `phases/03-barcode-decode/plan.md` | Replace placeholder with executed-plan summary (mirrors `phases/02-vision-extraction/plan.md` style) |
| `STATUS.md` | Update Phase 03 task table + set current focus to Phase 04 after merge |

---

## Out of scope (Phase 03)

- Library-based pixel decoding (pyzbar / zxing-cpp) — revisit only if Gemini
  proves unreliable on real tickets
- Barcode display in the draft keyboard (Phase 05 UX pass)
- Wallet pass construction (Phase 04)
- Dedup by barcode payload (Phase 04, as noted in multi-ticket design)
