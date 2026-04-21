# Phase 07 — Release pipeline

**Placeholder** — brainstorm with `/superpowers:brainstorming`.

## Scope
- `.github/workflows/ci.yml` — ruff + pytest on PRs.
- `.github/workflows/release.yml` — on `v*` tag: test → `production` env approval gate → `gcloud run deploy`.
- Create **`RELEASING.md`** (versioning, tags, rollback, env reference).
- Create **`.claude/commands/release.md`** (pre-flight → version bump PR → tag → monitor pipeline → post-deploy verify).
- Hardened `/ship` preview deploys (`--tag=pr-<N> --no-traffic`).
- Full end-to-end versioned release with a real tag.

## Superpowers checklist
- [ ] `/superpowers:brainstorming`
- [ ] `/superpowers:writing-plans`
- [ ] `/superpowers:test-driven-development`
- [ ] `/ship`
- [ ] `/release`
