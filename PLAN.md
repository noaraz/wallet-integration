# PLAN.md — Roadmap

Big-picture phase list. Each phase is a separate session: start with `/superpowers:brainstorming` in that phase's folder, then `/ship` when the phase's PR is ready.

| # | Phase | Folder | Outcome |
|---|---|---|---|
| 00 | Scaffold | [phases/00-scaffold](phases/00-scaffold) | Repo layout, hooks, commands, agents, skills, MVVM folders. **(This PR.)** |
| 01 | Telegram webhook | [phases/01-telegram-webhook](phases/01-telegram-webhook) | Webhook endpoint, signature verify, whitelist, `/start` `/help`, photo ack. **First Cloud Run deploy** (manual `gcloud run deploy`). |
| 02 | Vision extraction | [phases/02-vision-extraction](phases/02-vision-extraction) | Claude Vision extracts structured ticket fields from a photo. |
| 03 | Barcode decoding | [phases/03-barcode-decode](phases/03-barcode-decode) | Decode QR / Code128 / Aztec from the ticket image. |
| 04 | Google Wallet pass | [phases/04-wallet-pass](phases/04-wallet-pass) | Build `eventTicketObject`, sign JWT, produce save URL. `features/wallet-pass/` emerges. |
| 05 | End-to-end flow | [phases/05-end-to-end](phases/05-end-to-end) | Wire everything into the photo handler; "Add to Google Wallet" button in the reply. |
| 06 | Observability & hardening | [phases/06-observability](phases/06-observability) | JSON logs, error reporting, per-user quotas, retries, friendly errors. |
| 07 | Release pipeline & automated deploy | [phases/07-release-pipeline](phases/07-release-pipeline) | Create `RELEASING.md` + `.claude/commands/release.md`. `ci.yml` + `release.yml` with `production` approval gate → `gcloud run deploy`. End-to-end versioned deploys. |

## Deployment touchpoints across the roadmap

| When | What ships | How |
|---|---|---|
| End of Phase 01 | First live webhook | Manual `gcloud run deploy` via the `deploy-cloud-run` skill. Register webhook URL with Telegram. |
| End of Phase 04 | Wallet pass build working end-to-end locally | No prod deploy — validated via `wallet-pass-preview` skill on a phone. |
| End of Phase 05 | Full photo → wallet-pass flow on the live bot | Manual `gcloud run deploy`; smoke-test with a real screenshot. |
| End of Phase 07 | Automated deploys | GitHub Actions `release.yml` on tag → approval gate → `gcloud run deploy`. `/release` command goes live. |

Until Phase 07, each phase uses `/ship` for PRs but **deploys are triggered manually** (documented at the top of each phase's `plan.md`).

---

See [CLAUDE.md](CLAUDE.md) for architecture and conventions, [STATUS.md](STATUS.md) for current state. `RELEASING.md` lands in Phase 07.
