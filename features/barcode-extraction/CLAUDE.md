# Barcode Extraction — Feature Reference

Canonical reference for the barcode extraction feature. Read this when working on
`barcode_service.py`, `gemini_vision.py`, or `photo_handler.py`.

---

## Architecture

```
photo_handler.py
  ├── vision.extract(image_bytes)   → ExtractedTicket (text fields only, barcode=None)
  └── decoder.decode(image_bytes)   → BarcodeResult | None
        ↓ merged: ticket.barcode = result
```

The `BarcodeDecoderProtocol` facade (`barcode_service.py`) makes the decoder swappable —
same pattern as `VisionServiceProtocol` in `vision_service.py`.

## Key Decisions

**zxing-cpp is the barcode decoder.**
Ships as a self-contained Python wheel — no `apt-get` system deps needed in the Dockerfile.
The underlying C++ ZXing library is actively maintained (2024 releases).

**Gemini does NOT decode barcodes.**
`STRUCTURED_PROMPT` in `gemini_vision.py` contains no barcode instructions.
`GeminiVisionService._extract_sync` forces `barcode=None` on all return paths —
even if Gemini somehow populates the field, it is discarded. Gemini owns human-readable
text fields only; the decoder owns machine-readable payloads.

**Silent fallback to `None` when no barcode is found.**
`decoder.decode()` returns `None` if zxing-cpp finds nothing in the image.
`ticket.barcode = None` is the normal state for tickets without a scannable code.
No user-facing warning is shown.

**`barcode_value` is excluded from INFO logs (PII-adjacent).**
May contain signed tokens or booking references. `barcode_type` is safe to log.
See `callback_handler.py` for the log exclusion pattern.

## Key Files

| File | Role |
|---|---|
| `src/wallet_bot/services/barcode_service.py` | `BarcodeDecoderProtocol`, `ZxingBarcodeDecoder`, `create_default_decoder()` |
| `src/wallet_bot/services/gemini_vision.py` | Stripped `STRUCTURED_PROMPT`; `barcode=None` forced in `_extract_sync` |
| `src/wallet_bot/handlers/photo_handler.py` | Calls `decoder.decode(image_bytes)` after `vision.extract`; sets `ticket.barcode` |
| `src/wallet_bot/main.py` | Lazy-init `barcode_decoder` on `app.state`; `get_decoder()` dependency |
| `src/wallet_bot/models/ticket.py` | `BarcodeResult(barcode_type, barcode_value)`; `barcode_value` normalised to `None` if empty |
| `tests/unit/services/test_barcode_service.py` | Unit tests for `ZxingBarcodeDecoder` (zxing_cpp mocked) |

## Gotchas

**`_ZXING_FORMAT_MAP` in `barcode_service.py`**
Maps zxing-cpp CamelCase format names (`"QRCode"`, `"Code128"`, `"PDF417"`) to the
uppercase-underscore strings (`"QR_CODE"`, `"CODE_128"`, `"PDF_417"`) that
`wallet_service._BARCODE_TYPE_MAP` expects. Unknown formats fall back to `.upper()`.

**`barcode_value` normalisation**
`BarcodeResult` has a `@field_validator` that converts `""` to `None`. zxing-cpp
returns an empty string for some edge cases; `None` is the canonical "no value" state.

**Pydantic mutability**
`ExtractedTicket` is not frozen (`model_config` has no `frozen=True`), so
`ticket.barcode = await decoder.decode(image_bytes)` is safe direct attribute assignment.

## Swapping the Decoder Backend

Replace `ZxingBarcodeDecoder` in `barcode_service.py` and update `create_default_decoder()`.
No other file needs to change — all callers use `BarcodeDecoderProtocol`.
