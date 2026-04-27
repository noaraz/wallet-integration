# Phase 04 — Google Wallet pass build + JWT

**Placeholder** — brainstorm with `/superpowers:brainstorming`.

## Scope
- GCP setup doc: enable Wallet API, issuer, Event Ticket class, service account, `roles/walletobjects.writer`.
- `features/wallet-pass/` emerges: class def, object builder, RS256 JWT signer.
- Build `save_url = "https://pay.google.com/gp/v/save/" + jwt`.
- Validate via the `wallet-jwt-validator` agent.
- Create `wallet-pass-preview` skill via `/superpowers:writing-skills`.
- **Multi-ticket-per-event handling** (see CLAUDE.md): use a deterministic
  `eventTicketClass` id derived from event name+venue+date so N tickets for
  the same event auto-group under one class with N objects. No extra UX
  needed in Phase 02. Resolve duplicate-barcode dedup here too.

## Superpowers checklist
- [ ] `/superpowers:brainstorming`
- [ ] `/superpowers:writing-plans`
- [ ] `/superpowers:test-driven-development`
- [ ] `/ship`
