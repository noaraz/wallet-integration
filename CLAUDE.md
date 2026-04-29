# CLAUDE.md — wallet-integration

Personal Telegram bot that converts ticket screenshots into Google Wallet passes.

**Pipeline:** Telegram photo → Claude Vision extracts ticket fields → Python lib decodes QR/barcode → signed JWT for Google Wallet `eventTicketObject` → bot replies with an "Add to Google Wallet" link.

Track progress in **[STATUS.md](STATUS.md)**. Update it at the end of each phase.
Roadmap in **[PLAN.md](PLAN.md)** — phase list + links into `phases/NN-*/plan.md`.
Release process (`RELEASING.md` + `/release` command) lands in **Phase 07**.

---

## Branching & protection

- **`main` is protected**: PR required, no force-push, no deletion, linear history, conversation resolution required.
- **Never commit to `main` directly.** Every change lands via a PR from a feature branch.
- Branch names: `feat/<short-slug>`, `fix/<short-slug>`, `chore/<short-slug>`, `release/<version>`.
- One logical change per PR. `/ship` (`.claude/commands/ship.md`) drives the PR flow; `/release` drives versioned deploys.

---

## Architecture — Layered architecture

The bot uses a simple layered architecture guided by SOLID principles and dependency injection. Keep layers honest — don't let Telegram primitives leak into services, and don't let services call back up into handlers.

```
src/wallet_bot/
├── main.py              # FastAPI app, DI wiring, routes
├── config.py            # pydantic-settings, reads env → Secret Manager in prod
├── models/              # Pure domain data (no I/O, no framework types)
├── services/            # External integrations (Telegram Bot, Claude Vision, Wallet API)
└── handlers/            # Request handlers — one per Telegram update type; thin orchestration
```

| Layer | Knows about | Does NOT know about |
|---|---|---|
| **Models** | Python types only | Telegram, HTTP, anything external |
| **Services** | External APIs, models | Telegram update shape, handlers |
| **Handlers** | Models, services | FastAPI internals, HTTP response details |
| **main.py** | FastAPI routes, handlers, DI wiring | Handler or service internals |

**Flow for a photo update:**
1. `main.py` verifies webhook secret, parses the update, checks the whitelist.
2. Routes photo → `handlers/photo_handler.py`.
3. Handler calls the relevant services (vision, barcode, wallet) and returns a domain result (e.g. `TicketPassReady(event_name, save_url, barcode_payload)` or `TicketPassError(reason)`).
4. Handler formats and sends the Telegram reply via `services/telegram_client.py`.

Each handler must be unit-testable with only fake services — no live Telegram instance required.

**Feature documentation:** Per-feature decisions, gotchas, and key files live under
`features/<name>/CLAUDE.md`. Current features: [`features/barcode-extraction/`](features/barcode-extraction/CLAUDE.md).

---

## Best practices

- **Test-Driven Development is required.** Every feature, bugfix, and refactor follows `/superpowers:test-driven-development`: write a failing test first (RED), make it pass with the minimum code (GREEN), then clean up (REFACTOR). No production code without a failing test that motivated it. No skipping the RED step.
- **Type hints on every public function.** Keep `mypy --strict` passing once introduced (Phase 7).
- **Pydantic v2** for models; **pydantic-settings** for config. No `os.environ[...]` outside `config.py`.
- **Async-first** for all I/O (Telegram, Anthropic, Wallet API). Sync code only for pure computation.
- **Dependency injection** via constructor args or `main.py` wiring. No module-level singletons holding clients.
- **No secrets in code** — all via `config.py` → env → Google Secret Manager in prod. See `.env.example`.
- **Error handling**: no bare `except:`. Catch only what the layer handles; surface user-facing errors from handlers, not services.
- **Logging**: structured JSON, one line per event (Phase 6 onward). Never log raw tokens or barcode payloads at INFO+.
- **Tests**: `tests/unit/` mirrors `src/` layout. Services get integration tests with mocked HTTP. Target ≥80% coverage from Phase 2.
- **Commits**: conventional style (`feat:`, `fix:`, `chore:`, `docs:`, `test:`). One logical change per commit.
- **Small files**: if a module approaches ~300 lines, it's doing too much — split by layer first.
- **No premature abstraction**: three similar lines is fine. Abstract on the fourth, not the second.

---

## Local dev

**Everything runs in Docker. Do not `pip install` on the host.**

```bash
docker compose build                                    # build the dev image
docker compose run --rm bot pytest -v                   # run the test suite
docker compose run --rm bot ruff check src/ tests/      # lint
docker compose run --rm bot ruff format src/ tests/     # format
docker compose run --rm bot bash                        # interactive shell in the container
```

Source and tests are bind-mounted into the container, so edits on the host are picked up immediately. Rebuild (`docker compose build`) only when `pyproject.toml` or `Dockerfile` changes.

Running the bot locally against Telegram requires a public HTTPS URL — use `ngrok http 8080` pointing at `docker compose up` and register the URL via the `tg-webhook-register` skill (once created in Phase 01).

---

## Adding a new phase

Each phase lives under `phases/NN-<slug>/` with its own `plan.md` and `CLAUDE.md`. Use `.claude/commands/new-phase.md` to scaffold one. Start each phase with `/superpowers:brainstorming` in a fresh session, then `/ship` when done.

### Adding a project skill

Project-specific skills live under `.claude/skills/<skill-name>/SKILL.md`. **Always create skills via `/superpowers:writing-skills`** — which enforces a TDD cycle: write a failing pressure test first, write the minimum skill that makes it pass, then refactor to close loopholes. Frontmatter must be just `name` + `description` (starting with "Use when…", not a workflow summary).

Planned skills, deferred to the phase where they become concrete:
- `deploy-cloud-run` — Phase 01 (when there's a real service to deploy).
- `tg-webhook-register` — Phase 01 (when there's a webhook URL to register).
- `wallet-pass-preview` — Phase 04 (when there's a JWT builder to preview).

---

## Superpowers workflow (default)

This project uses the `superpowers` skill plugin. **Every session invokes `/superpowers:using-superpowers` at start** (it's loaded automatically by the harness, but confirm via the SessionStart hook message). The key workflows to follow:

| When | Skill to invoke |
|---|---|
| Starting any session | `/superpowers:using-superpowers` (auto-loaded) — establishes how to find/use skills |
| Starting a new phase or feature | `/superpowers:brainstorming` → produces a design doc |
| After design approval | `/superpowers:writing-plans` → produces an implementation plan |
| Executing a plan in a fresh session | `/superpowers:executing-plans` |
| Executing a plan in the current session | `/superpowers:subagent-driven-development` |
| Implementing any feature/bugfix | `/superpowers:test-driven-development` (RED → GREEN → REFACTOR) |
| Debugging a failure | `/superpowers:systematic-debugging` |
| Before claiming "done" | `/superpowers:verification-before-completion` |
| Isolating feature work | `/superpowers:using-git-worktrees` |
| Finishing a branch | `/superpowers:finishing-a-development-branch` + local `/ship` |
| Independent parallel subtasks | `/superpowers:dispatching-parallel-agents` |

**Rule of thumb:** if a superpowers skill matches a task even 1% — invoke it. See `using-superpowers` for the red-flag thoughts that signal rationalizing past it.

**Project-specific commands** complement the superpowers flow:
- `/ship` (`.claude/commands/ship.md`) — runs tests + lint + audit, opens the PR, dispatches the reviewer agent.
- `/new-phase` (`.claude/commands/new-phase.md`) — scaffold a `phases/NN-<slug>/` folder.
- `/release` — not created yet; added in **Phase 07** when the deploy pipeline exists.
