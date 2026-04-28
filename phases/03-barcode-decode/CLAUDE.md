# Phase 03 — Barcode decoding

## Key decisions

- **No barcode library.** Gemini Vision reads QR codes directly. Revisit
  only if real-world tickets prove unreliable (binary Aztec payloads etc.).
- **`barcode_value` excluded from INFO logs** — treat it as PII-adjacent
  (may be a signed token). `barcode_type` is safe metadata and stays.
- **Silent fallback** when `barcode is None` — no user-facing warning.
  Phase 04 decides whether a barcode is required for the wallet pass.

## Gotchas

- `docker-compose.yml` runs `bash`, not uvicorn — use `docker run` with
  `-p 8080:8080 --env-file .env` for local manual testing (see
  `.claude/skills/tg-local-testing/SKILL.md`).
- Webhook path is `/telegram/webhook`, not `/webhook`.
- `BarcodeResult` uses `barcode_type` / `barcode_value` (not `type` /
  `value`) to avoid shadowing `builtins.type` for `mypy --strict` (Phase 07).
