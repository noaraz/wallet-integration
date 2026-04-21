# /new-phase — Scaffold a new phase folder

Use when starting a new phase of the roadmap. Creates `phases/NN-<slug>/{plan.md, CLAUDE.md}` from a template and adds a row to `PLAN.md`.

---

## 1. Ask for inputs

Use `AskUserQuestion`:

```
Question: "What's the next phase number and slug?"
Header: "New phase"
Options:
  - "NN-<slug>" — e.g. "08-rate-limits"
```

(Free-text; user provides the full folder name.)

Also ask for a one-line outcome description (what the phase delivers).

---

## 2. Create the folder and files

```bash
NN_SLUG="<from-user>"
mkdir -p "phases/${NN_SLUG}"
```

Write `phases/${NN_SLUG}/plan.md`:

```md
# Phase <NN> — <title>

**Placeholder** — brainstorm with `/superpowers:brainstorming`.

## Scope
- <what this phase delivers>

## Superpowers checklist
- [ ] `/superpowers:brainstorming`
- [ ] `/superpowers:writing-plans`
- [ ] `/superpowers:test-driven-development`
- [ ] `/superpowers:verification-before-completion`
- [ ] `/ship`
```

Write `phases/${NN_SLUG}/CLAUDE.md`:

```md
# Phase <NN> — notes (placeholder)

Populated during the phase's brainstorming session.
```

---

## 3. Add a row to `PLAN.md`

Insert a new row in the roadmap table with the phase number, title, folder link, and outcome.

---

## 4. Update STATUS.md

Add a `⬜ not started` row under "Phase status".

---

## 5. Commit on a new branch

```bash
git checkout -b chore/phase-<NN>-scaffold
git add phases/${NN_SLUG}/ PLAN.md STATUS.md
git commit -m "chore: scaffold phase <NN> — <title>"
```

Tell the user: "Open a fresh session in `phases/${NN_SLUG}/` and run `/superpowers:brainstorming` to design the phase."
