# Project Status

**Last updated:** 2026-09-22 (status-check session) · **Last commit:** none yet — nothing committed to git so far

## Active
- Nothing in progress right now; waiting on the user to add a real `ANTHROPIC_API_KEY` and run the app end-to-end with live data.

## Status-check session (2026-09-22)
Re-verified against the case-study brief (`references/hasamex_project.pdf`) and `Interview_Guide.txt` — all 5 required capabilities (interview-guide answers, exact quotes, timestamps, cross-expert themes/disagreements, free-form Q&A) are implemented and traceable per `CLAUDE.md`'s architecture. Ran the full verification matrix and found it green except two frontend lint issues, now fixed:
- Backend: `pytest` 16/16 passing, `ruff check` clean, `mypy` clean.
- Frontend: `vitest` 5/5 passing, `tsc --noEmit` clean, `next build` succeeds.
- Fixed `frontend/src/components/ExpertQAPanel.tsx`: the fetch-on-`activeId`-change effect called `setLoading(true)`/`setError(null)` synchronously at the top of the effect body, tripping the new `react-hooks/set-state-in-effect` rule (and, more substantively, could flash the *previous* expert's stale answers while the new one loaded). Replaced the separate `loading` boolean with state derived from comparing `data.expert_id`/`error.id` against `activeId`, and gated the data block on `data.expert_id === activeId` — no more synchronous resets, no more stale-data flash.
- Fixed `frontend/src/components/ErrorBoundary.tsx`: removed a dead `eslint-disable-next-line no-console` (that rule isn't enabled in this project's config, so it was flagged as unused).
- `ThemesPanel.tsx` and `app/page.tsx` have similar fetch-effects but weren't flagged (no dependency-driven reset), so left as-is rather than introducing a shared hook the codebase doesn't otherwise need.

## Done
- Analyzed the Hasamex AI Engineer case study (JD): build an app that analyzes 3 expert-call transcripts with per-expert Q&A, exact quotes + timestamps, cross-expert themes/disagreements, and free-form Q&A — all traceable, no hallucination.
- Researched reference repos (`anthropic/claude-cookbooks`, `anthropic/claude-quickstarts`, `anthropic/claude-agent-sdk-python`) to inform architecture — see [README.md](README.md) for the writeup.
- Built the full app: FastAPI backend (`backend/`) + Next.js/Tailwind frontend (`frontend/`), grounded via Anthropic's native Citations API, with a verbatim-quote guardrail as a second grounding layer.
- Added a pluggable multi-provider layer (`backend/app/providers/`): Anthropic (Citations API, production default) plus an OpenAI-compatible path for Groq/HF open-weight models (e.g. `openai/gpt-oss-120b`) for high-volume/rate-limit-friendly dev and eval work.
- Production-hardened the backend: typed settings, retries/backoff, structured logging, clean error handling, pytest suite (16 tests, all passing, no network calls), ruff+mypy clean, an eval harness (`backend/evals/`) with grounded + "trap" (should-refuse) cases.
- Hardened the frontend: ErrorBoundary, Vitest+RTL tests, Prettier, `.env.example`.
- Added CI (`.github/workflows/ci.yml`), pre-commit hooks, and multi-stage Dockerfiles + `docker-compose.yml` for both services.
- Set up a project-scoped `.mcp.json` (github, context7, playwright, sequential-thinking) — the only 4 MCP servers actually necessary for this kind of work, kept deliberately minimal after finding and removing pre-synced-but-broken/unused plugin clutter (marketing/productivity/design/grafana-cloud-mcp) from the account.
- Tried a hand-built global skills/agents layer, then replaced it: found and installed `superpowers` (obra/superpowers, 289k★, officially in Anthropic's plugin marketplace) — a mature, evidence-based development methodology (brainstorm → plan → subagent-driven TDD implementation → review → finish-branch) with parallel-agent dispatch and self-diagnosis, superseding the hand-rolled domain-checklist skills, which were deleted.
- Added verified, repo-scoped hooks (`.claude/settings.json`): edits to `backend/**/*.py` auto-run ruff format+check, edits to `frontend/src/**/*.{ts,tsx,js,jsx,css,json}` auto-run prettier — pipe-tested against this repo's actual tool locations (a generic global version of this hook doesn't work reliably).
- Added `CLAUDE.md` (durable guidance: commands + architecture) via the built-in `init` skill.

## Next
1. User adds a real `ANTHROPIC_API_KEY` to `backend/.env` and runs the full stack once against live data to sanity-check answer quality.
2. Record the required demo video (architecture, model choice, citation/timestamp handling, hallucination mitigation, 3→30+ scaling story — all already written up in [README.md](README.md)).
3. First git commit + push to a repo, once the user confirms they're ready (nothing has been committed yet — only created locally).
4. Submit before the deadline: **25 Sept 2026, 11:00 IST**.

## Blocked / open questions
- None currently — the only gate is the user providing their own API key, which isn't something to do on their behalf.
