# /ship — Feature Ship Workflow

Run this when a feature branch is ready to land on `main` via PR. Follow the steps in order. **`main` is protected** — never push to it directly; everything goes through a PR.

---

## 1. Run tests

All tooling runs in Docker — never call `pytest`/`ruff`/`pip-audit` directly on the host.

```bash
docker compose run --rm bot pytest tests/ -v --cov=src --cov-report=term-missing
```

Present: total passed/failed, coverage per module, any failures.

Every feature must have followed `/superpowers:test-driven-development`. If coverage on changed files is below 80%, add tests before continuing.

---

## 2. Lint

```bash
docker compose run --rm bot ruff check src/ tests/
docker compose run --rm bot ruff format --check src/ tests/
```

Auto-fix where safe:
```bash
docker compose run --rm bot ruff check --fix src/ tests/
docker compose run --rm bot ruff format src/ tests/
```

---

## 3. Security audit

```bash
docker compose run --rm bot pip-audit
```

Triage any new high-severity findings before opening the PR.

Also dispatch the `secret-scanner` agent against the staged diff:

```
Agent tool: subagent_type="secret-scanner"
Prompt: "Scan the staged diff for API keys, JWT private keys, Telegram bot tokens, Google service-account credentials, or any other secret. Report file:line for each finding."
```

Block the PR if anything is found. Fix (move to env + Secret Manager) and re-run.

---

## 4. Ask what to fix (pre-PR)

Show test + lint + audit results and ask:

> "All green. Anything to fix before I open the PR?"

Wait for the user's response. Fix any requested items, re-run the affected tests, then continue.

---

## 5. Update docs

- **STATUS.md** — mark completed tasks ✅, bump "Last updated", set "Current Focus" to the next phase.
- **CLAUDE.md** — add any new patterns, gotchas, or conventions discovered.
- **`phases/NN-<slug>/plan.md`** — check off completed items, note deviations.
- **`phases/NN-<slug>/CLAUDE.md`** — record phase-specific gotchas.

---

## 6. Commit and open PR

```bash
git add -A
git status
git commit -m "feat: <short description>"
```

### Ask about preview deploy

Use `AskUserQuestion`:

```
Question: "Deploy a Cloud Run preview revision for this PR?"
Header: "Preview"
Options:
  - Yes — `gcloud run deploy --tag=pr-<N> --no-traffic`, surface the tagged URL in the PR body
  - No  — open the PR without a preview deploy
```

If Yes, deploy via the `deploy-cloud-run` skill (once it exists, starting Phase 01) with `--tag=pr-<PR_NUMBER> --no-traffic`. Before the skill lands, run `gcloud run deploy` manually with the same flags and surface the tagged URL.

### Create the PR

```bash
git push -u origin $(git branch --show-current)
gh pr create \
  --base main \
  --title "feat: <title>" \
  --body "$(cat <<'EOF'
## Summary
- <bullet 1>
- <bullet 2>

## Test plan
- [ ] `pytest tests/ -v --cov=src`
- [ ] `ruff check src/ tests/`
- [ ] Preview URL reachable (if preview deployed): <URL>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Return the PR URL to the user.

---

## 7. Code review on the PR

Invoke the project reviewer agent:

```
Agent tool: subagent_type="reviewer"
Prompt: "Review this PR: <URL>. Check MVVM layering (no service imports in views, no telegram shapes in services), type hints, error handling, and test coverage on changed files."
```

Present findings to the user and offer to fix them.

---

## 8. Wait for CI + merge

Watch CI until it completes (CI runs in GitHub Actions, not Docker — `gh` is a GitHub CLI, OK to run on host):

```bash
gh run watch $(gh run list --branch "$(git branch --show-current)" --limit 1 --json databaseId -q '.[0].databaseId')
```

When green, tell the user:

> CI passed on PR #<N>. Ready to merge when you are.

Do not merge for the user — `main` is protected and merging is a deliberate user action.
