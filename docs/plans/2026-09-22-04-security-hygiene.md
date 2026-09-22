# Phase 4: Security & Repo Hygiene — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining cheap, genuinely-missing repo-hygiene items: dependency vulnerability scanning, secret scanning in CI, and deleting confirmed-unreferenced starter assets.

**Architecture:** No application code changes — this phase is entirely CI config and one file deletion. Deliberately small: the CSP header (originally planned for this phase) already landed in Phase 2 Task 4, and `npm ci` enforcement turned out to already exist in `.github/workflows/ci.yml` (both corrections made during spec review — see `design/SECURITY_CHECKLIST.md`).

**Tech Stack:** GitHub Actions, Dependabot, gitleaks.

**Spec:** `docs/superpowers/specs/2026-09-22-frontend-redesign-design.md` §11. Full reasoning in `design/SECURITY_CHECKLIST.md`.

## Global Constraints

- No application code touched in this phase — verify with `git diff --stat` after each task that only `.github/` and asset files changed.
- Can run in parallel with Phase 3 (Observability) — neither touches the same files as the other, and neither depends on the other's output. Sequenced here after Phase 3 only to match the user's requested reading order, not because of a real dependency.

---

## File Structure

- Create: `.github/dependabot.yml`
- Modify: `.github/workflows/ci.yml` (add a `security` job)
- Delete: `frontend/public/file.svg`, `frontend/public/globe.svg`, `frontend/public/next.svg`, `frontend/public/vercel.svg`, `frontend/public/window.svg`

---

### Task 1: Dependabot configuration

**Files:**
- Create: `.github/dependabot.yml`

**Interfaces:**
- Produces: automated weekly PRs for npm (frontend) and pip (backend, via the `uv`-compatible `pip` ecosystem type — Dependabot doesn't have a distinct `uv` ecosystem as of this writing; it reads `pyproject.toml` under the `pip` type) and GitHub Actions dependency updates.

- [ ] **Step 1: Write the config**

```yaml
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule:
      interval: "weekly"

  - package-ecosystem: "pip"
    directory: "/backend"
    schedule:
      interval: "weekly"

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

- [ ] **Step 2: Validate the YAML**

Run: `python -c "import yaml; yaml.safe_load(open('.github/dependabot.yml'))"` (or any YAML validator available) — confirms syntactically valid before committing something GitHub will otherwise silently ignore if malformed.

- [ ] **Step 3: Commit**

```bash
git add .github/dependabot.yml
git commit -m "chore: add Dependabot config for npm, pip, and GitHub Actions

Baseline dependency-vulnerability scanning for a public GitHub repo —
currently absent entirely. Weekly schedule across all three ecosystems
this repo actually uses."
```

---

### Task 2: `gitleaks` secret scanning in CI

**Files:**
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: a new `security` job in the existing CI workflow, running alongside (not blocking) `backend`/`frontend`.

- [ ] **Step 1: Add the job**

In `.github/workflows/ci.yml`, add a third job alongside `backend` and `frontend`:
```yaml
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 2: Verify the workflow file is still valid YAML**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
Expected: no error.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add gitleaks secret scanning job

Supplementary to GitHub's own native secret scanning on public repos —
current baseline for custom-pattern detection and CI-level enforcement,
not just relying on GitHub's automatic scan."
```

(This job's actual pass/fail can only be observed once pushed to GitHub and run — note in the PR/commit that follows this task that it should be watched on the next push, not assumed clean from local validation alone.)

---

### Task 3: Delete unused starter assets

**Files:**
- Delete: `frontend/public/file.svg`, `frontend/public/globe.svg`, `frontend/public/next.svg`, `frontend/public/vercel.svg`, `frontend/public/window.svg`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing — pure deletion, confirmed dead weight, not a design decision.

- [ ] **Step 1: Re-confirm they're unreferenced** (already checked once during the audit — re-verify here since deletions should never be taken on faith, same discipline as Phase 1 Task 3's endpoint deletion):

Run: `grep -rn "file.svg\|globe.svg\|next.svg\|vercel.svg\|window.svg" frontend/src`
Expected: no matches.

- [ ] **Step 2: Delete them**

```bash
git rm frontend/public/file.svg frontend/public/globe.svg frontend/public/next.svg frontend/public/vercel.svg frontend/public/window.svg
```

- [ ] **Step 3: Verify the build still succeeds**

Run: `npm run build` (from `frontend/`)
Expected: succeeds — these were never referenced, so nothing should break.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(frontend): remove unused create-next-app starter assets

Confirmed unreferenced anywhere in the app (grepped before deleting,
not assumed). create-next-app's default placeholder icons, dead
weight since this project's own icon work started."
```

---

## Phase 4 Completion Check

Before starting Phase 5:
- [ ] `.github/dependabot.yml` and the `security` CI job are committed.
- [ ] `npm run build` still succeeds after the asset deletion.
- [ ] Reminder, not a task: the Anthropic workspace spend limit (spec §11 — "yours to do") is still outstanding and isn't something any task in this plan can complete on your behalf. Set it before adding a real `ANTHROPIC_API_KEY` to `backend/.env`.
