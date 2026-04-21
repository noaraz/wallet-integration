# Phase 04 — Google Wallet pass build + JWT

**Placeholder** — brainstorm with `/superpowers:brainstorming`.

## Scope
- GCP setup doc: enable Wallet API, issuer, Event Ticket class, service account, `roles/walletobjects.writer`.
- `features/wallet-pass/` emerges: class def, object builder, RS256 JWT signer.
- Build `save_url = "https://pay.google.com/gp/v/save/" + jwt`.
- Validate via the `wallet-jwt-validator` agent.
- Create `wallet-pass-preview` skill via `/superpowers:writing-skills`.

## Superpowers checklist
- [ ] `/superpowers:brainstorming`
- [ ] `/superpowers:writing-plans`
- [ ] `/superpowers:test-driven-development`
- [ ] `/ship`
