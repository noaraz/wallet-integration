# Phase 05 — notes

## Open design questions (to resolve during brainstorming)

### Multi-ticket UX

Phase 02 ships with a one-photo-per-flow draft store (one `DraftState` per
`chat_id`). Phase 04 handles the technical side of multiple tickets per
event via a deterministic `eventTicketClass` id (see
`phases/04-wallet-pass/CLAUDE.md`), so a user who sends 4 photos one at a
time already gets 4 wallet objects under a single shared class — for free,
without changes to Phase 02.

The Phase 05 design choice is purely UX. Three options to weigh during
brainstorming:

- **A. Sequential (default).** User sends one photo, approves, sends the
  next. Simplest, zero new state, works today after Phase 04 ships.
- **B. Batch / album.** User sends a Telegram media-group (multiple photos
  in one message) → bot collects them, extracts in parallel, shows a
  combined summary, single approval emits N save links (or one batch save
  URL — Google Wallet supports multi-object save). Requires `DraftStore`
  keyed `(chat_id, draft_id)` and a "session" concept.
- **C. Inferred grouping.** Same flow as A on the surface, but the bot
  notices when a new photo's event details match a recently approved
  draft and offers to add it to the same "trip" with one tap. Magic when
  it works, confusing when it misfires.

**Default to A unless real use proves it clunky.** If we go to B, it's a
~30-LOC change to `DraftStore` plus a new "I'm done, build my passes"
button.

### Other Phase 05 design points (TBD during brainstorming)

- Fallbacks when fields are missing (no event name → ask user; no barcode
  → include raw text as pass description).
- Save-link format: inline URL button vs raw URL in text.
- Error budget: how many extraction retries before surfacing failure to
  the user.
