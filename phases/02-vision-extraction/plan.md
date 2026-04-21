# Phase 02 — Vision extraction

**Placeholder** — brainstorm with `/superpowers:brainstorming`.

## Scope (from root PLAN.md)
- Download Telegram photo → bytes (no disk).
- Call Claude Vision with a structured-output prompt: `{event_name, venue, start_datetime, seat, section, row, confirmation_number, raw_text}`.
- Pydantic model; all fields `Optional` (OCR may miss some).
- Default to Haiku-first for cost; fall back to Sonnet on low-confidence extractions.
- Tests against fixture screenshots.

## Superpowers checklist
- [ ] `/superpowers:brainstorming`
- [ ] `/superpowers:writing-plans`
- [ ] `/superpowers:test-driven-development`
- [ ] `/ship`
