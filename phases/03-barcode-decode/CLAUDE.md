# Phase 03 — Barcode decoding (phase history)

> **Moved.** Canonical feature reference is at
> [`features/barcode-extraction/CLAUDE.md`](../../features/barcode-extraction/CLAUDE.md).
> This file is retained for phase delivery history only.

## Original key decisions (superseded)

- **No barcode library** — Gemini Vision read QR codes directly.
  Superseded: E2E testing showed inaccurate results; replaced by `zxing-cpp` + `BarcodeDecoderProtocol`.

## Decisions still valid (see canonical doc)

- `barcode_value` excluded from INFO logs (PII-adjacent).
- Silent fallback when `barcode is None` — no user-facing warning.
- `BarcodeResult` uses `barcode_type` / `barcode_value` (not `type` / `value`) to avoid
  shadowing `builtins.type` for `mypy --strict` (Phase 07).
