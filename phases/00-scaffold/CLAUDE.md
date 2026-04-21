# Phase 00 — Scaffold notes

Conventions established here that every later phase must respect:

- **Protected main, PR-only workflow** (see root `CLAUDE.md` → "Branching & protection").
- **MVVM layering** under `src/wallet_bot/` — models / services / viewmodels / views. Don't cross the lines.
- **Per-phase folder**: every new phase gets `phases/NN-<slug>/{plan.md, CLAUDE.md}`, scaffolded via `.claude/commands/new-phase.md`.
- **Superpowers-first**: start each phase with `/superpowers:brainstorming`, implement via `/superpowers:test-driven-development`, ship with `/ship`.
- **No runtime deps in Phase 0** — each phase adds the specific Python libs it needs.

If you find yourself wanting to change any of the above, stop and discuss — these are load-bearing for the whole roadmap.
