# Phase 00 — Scaffold

## Context

Bootstrap the repo so every later phase has a clear place to land. Produce the directory layout, MVVM source tree, Claude Code config (hooks/commands/agents/skills), and root markdowns, all behind a protected-main + PR workflow.

## Scope

- Baseline commit on `main` + branch protection (PR required, no force-push, linear history).
- Feature-branch PR (`feat/phase-0-scaffold`) with:
  - Root markdowns: `CLAUDE.md`, `PLAN.md`, `STATUS.md`, `README.md`. (`RELEASING.md` deferred to Phase 07.)
  - `pyproject.toml` with dev deps (pytest, ruff) only — runtime deps added per phase.
  - `Dockerfile` skeleton for Cloud Run; real entrypoint added in Phase 1.
  - `.dockerignore`, `.gitignore`, `.env.example`.
  - MVVM source tree under `src/wallet_bot/{models,services,viewmodels,views}/`.
  - `tests/` with a smoke test for `healthz()`.
  - `phases/00..07/` with `plan.md` + `CLAUDE.md` (this one is full, the others are stubs).
  - `hooks/{pre_edit_guard.sh, post_python_edit.sh, start.sh}`.
  - `.claude/settings.json`, `.claude/commands/{ship,new-phase}.md` (`release.md` deferred to Phase 07), `.claude/agents/{reviewer,secret-scanner,wallet-jwt-validator}.md`.
  - Skills (`deploy-cloud-run`, `tg-webhook-register`, `wallet-pass-preview`) are **deferred**: each is written via `/superpowers:writing-skills` in the phase that first needs it (01, 01, 04 respectively).

## Out of scope

- Any runtime behavior (web server, Telegram, Vision, barcode, Wallet) — those are Phases 1–4.
- CI/CD workflows — those are Phase 7 (stub `.github/workflows/` created then).

## Verification

All commands run inside Docker — nothing is installed on the host.

1. `docker compose build` succeeds.
2. `docker compose run --rm bot pytest -v` → 1 passed (the smoke test).
3. `docker compose run --rm bot ruff check src/ tests/` → no issues.
4. `git log main..HEAD` shows the scaffold commit on `feat/phase-0-scaffold`.
5. Main is protected: `gh api /repos/noaraz/wallet-integration/branches/main/protection` returns `required_pull_request_reviews`.
6. PR opens cleanly and can be merged into main only via the PR (not a direct push).
