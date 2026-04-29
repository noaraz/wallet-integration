# Barcode Extraction — Implementation Plan (zxing-cpp revision)

> **Revision (2026-04-29):** Original Phase 03 used Gemini to decode barcodes visually.
> E2E testing showed inaccurate results. This plan supersedes `phases/03-barcode-decode/plan.md`
> for implementation guidance; the phase plan is retained for delivery history.

## Context

Phase 03 shipped barcode extraction by embedding instructions in the Gemini prompt.
E2E testing revealed that Gemini performs visual OCR on binary pixel matrices — it guesses
rather than decodes, producing inaccurate QR values. This revision replaces the Gemini
approach with `zxing-cpp`, a proper binary barcode decoder, behind a `BarcodeDecoderProtocol`
facade for easy swapping.

---

## Dependencies added

`pyproject.toml` core deps:
- `zxing-cpp>=2.2` — self-contained wheel, no apt system deps
- `Pillow>=10` — image loading for the decoder (already in `eval` extra)

---

## Changes

### New: `src/wallet_bot/services/barcode_service.py`
- `BarcodeDecoderProtocol` — `async def decode(image_bytes) -> BarcodeResult | None`
- `ZxingBarcodeDecoder` — wraps `zxing_cpp.read_barcodes(PIL.Image)`; runs sync decode in `asyncio.to_thread`
- `_ZXING_FORMAT_MAP` — maps CamelCase format names to uppercase-underscore strings
- `create_default_decoder()` — production factory

### `src/wallet_bot/services/gemini_vision.py`
- Removed barcode instructions from `STRUCTURED_PROMPT`
- `_extract_sync` forces `barcode=None` via `model_copy` on both return paths

### `src/wallet_bot/models/ticket.py`
- Updated `BarcodeResult` docstring (decoder, not Gemini)

### `src/wallet_bot/handlers/photo_handler.py`
- Added `decoder: BarcodeDecoderProtocol` parameter
- `ticket.barcode = await decoder.decode(image_bytes)` inside the `typing_indicator` block

### `src/wallet_bot/main.py`
- Imported `BarcodeDecoderProtocol`, `create_default_decoder`
- `app.state.barcode_decoder = None` in lifespan (lazy init)
- `get_decoder(request)` dependency function
- Passes `decoder=get_decoder(request)` to `handle_photo`

### Tests
- New `tests/unit/services/test_barcode_service.py` (9 tests, zxingcpp mocked)
- `tests/unit/services/test_gemini_vision.py` — removed 3 stale barcode tests; added 2 new
- `tests/unit/handlers/test_photo_handler.py` — added `_FakeDecoder`; updated all calls; added 2 new tests
- `tests/unit/test_webhook_phase02.py` — added `patched_decoder` autouse fixture

---

## Verification

```bash
docker compose run --rm bot pytest -v          # 185 tests, all green
docker compose run --rm bot ruff check src/ tests/   # no issues
```

## Post-ship fixes (same PR)

- `zxingcpp` module rename: PyPI package `zxing-cpp` v3 ships as `zxingcpp` (no underscore) — updated import and all patch targets
- `_decode_sync` error handling: `Image.open` + `read_barcodes` wrapped in `try/except` → returns `None` on corrupt images
- PIL context manager: `with Image.open(...) as img`
- `scripts/eval_barcode.py` — standalone decode tool + wallet pass QR image output
