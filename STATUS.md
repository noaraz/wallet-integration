# STATUS.md — Progress Tracker

Last updated: 2026-04-19 — Phase 00 scaffold in progress

## Current Focus

**Phase 01 — Telegram webhook skeleton** (starts after this scaffold PR merges).

---

## Phase status

| # | Phase | Status |
|---|---|---|
| 00 | Scaffold | 🔄 in PR |
| 01 | Telegram webhook | ⬜ not started |
| 02 | Vision extraction | ⬜ not started |
| 03 | Barcode decoding | ⬜ not started |
| 04 | Google Wallet pass | ⬜ not started |
| 05 | End-to-end flow | ⬜ not started |
| 06 | Observability & hardening | ⬜ not started |
| 07 | Release pipeline | ⬜ not started |

Legend: ✅ done · 🔄 in progress · ⬜ not started

---

## Phase 00 — Scaffold 🔄

| Task | Status |
|------|--------|
| Baseline commit on main + branch protection | ✅ |
| Root markdowns (CLAUDE, PLAN, STATUS, README) | ✅ |
| MVVM source layout (`src/wallet_bot/{models,services,viewmodels,views}/`) | ✅ |
| pyproject.toml, Dockerfile, .dockerignore, .env.example | ✅ |
| Phase folders (00–07) with plan.md + CLAUDE.md | ✅ |
| Hooks (pre_edit_guard, post_python_edit, start) | ✅ |
| `.claude/commands/{ship,new-phase}.md` | ✅ |
| `.claude/commands/release.md` + `RELEASING.md` | ⬜ deferred to Phase 07 |
| `.claude/agents/{reviewer,secret-scanner,wallet-jwt-validator}.md` | ✅ |
| `.claude/skills/*` | ⬜ deferred — each skill is created (via `/superpowers:writing-skills`) in the phase that needs it |
| PR opened, CI green, merged to main | ⬜ |
