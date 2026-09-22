# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Backend** (from `backend/`, with `.venv` activated):
```bash
python -m venv .venv && .venv/Scripts/activate   # Windows; source .venv/bin/activate elsewhere
pip install -r requirements-dev.txt              # runtime + lint/type/test tooling
cp .env.example .env                             # then set ANTHROPIC_API_KEY (or GROQ/HF for LLM_PROVIDER)
uvicorn app.main:app --reload --port 8000

pytest -q                                        # full suite, no network calls (provider is mocked)
pytest tests/test_main_api.py::test_chat_grounds_answer_with_expert_specific_citation  # single test
ruff check app/ tests/ evals/ && ruff format app/ tests/ evals/
mypy app/
python -m evals.run_eval --compare anthropic groq   # real API calls — costs money, not part of pytest
```

**Frontend** (from `frontend/`):
```bash
npm install
npm run dev                                      # localhost:3000, expects backend on :8000
npm run build && npx tsc --noEmit && npm run lint
npm test                                         # vitest
```

**Both together**: `docker compose up --build` from repo root (requires `backend/.env` to exist first).

## Architecture

This app answers questions over 3 expert-call transcripts with every answer traceable to an exact quote + timestamp, and never inventing information not in the source. Two mechanisms carry that guarantee end to end:

**Provider abstraction (`backend/app/providers/`)** — a `Provider` protocol (`types.py`) with two implementations, selected at runtime via `LLM_PROVIDER` (`config.py`):
- `AnthropicProvider` (default): uses Claude's native Citations API. Citations are computed by the API against the literal document text sent, not generated freeform — a citation carries a document index and a char-offset span, never a paraphrase.
- `OpenAICompatibleProvider`: one class serving any OpenAI-chat-completions-compatible endpoint (Groq, HF Inference Providers) for open-weight models. These have no native citation feature, so this class enforces grounding itself — it prompts for verbatim quotes in a JSON response, then does a literal substring search against the source document; a quote that doesn't match verbatim is dropped, never shown. Used for the eval harness and fast dev iteration where Anthropic's rate limits slow things down.

Both implementations return the same `AskResult`/`RawCitation` shape, so nothing downstream needs to know which provider answered.

**Citation → timestamp resolution (`transcript_parser.py` + `main.py`)** — transcripts are parsed into `(timestamp, char_offset)` markers without altering the raw text at all, because a citation's char offset is only meaningful against the *exact* bytes sent to the provider. `main.py`'s `resolve_citations` maps a citation's offset to the nearest timestamp marker at-or-before it, and `verify_quote` is a second guardrail — every citation, from either provider, gets re-checked against the source transcript before being returned to the client; anything that fails is dropped rather than shown.

**Caching (`cache.py`)** — per-expert Q&A and cross-expert themes are computed once and cached as JSON to disk, since generating them means one Anthropic call per interview-guide question. Pass `?refresh=true` to bypass and recompute. The eval harness (`evals/`) is deliberately separate from `pytest`: evals make real, paid API calls against golden/trap cases and are run manually, never automatically.

**Frontend** is a single page (`app/page.tsx`) with three tabs (Expert Q&A, Themes & Disagreements, Ask a Question), each panel independently fetching from the backend and wrapped in its own `ErrorBoundary` so one broken panel doesn't blank the page.

**Hooks** (`.claude/settings.json`): edits to `backend/**/*.py` auto-run `ruff format` + `ruff check`; edits to `frontend/src/**/*.{ts,tsx,js,jsx,css,json}` auto-run `prettier --write`. Both are wired to this repo's actual tool locations (venv-installed ruff, local `node_modules` prettier) — a generic global version of this hook doesn't work reliably across different repo layouts.

## Status tracking

`PROGRESS.md` at the repo root is a hand-maintained, git-committed snapshot of what's done/active/next — check it at the start of a session to re-orient. Distinct from any Claude Code session state: it survives independent of the tool and is meant to be quickly skimmable.
