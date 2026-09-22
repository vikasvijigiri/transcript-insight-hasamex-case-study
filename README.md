# Transcript Insight — Hasamex AI Engineer Case Study

An app that analyses 3 expert-call transcripts (France / Germany / UK, robotic surgery market) and:

- answers the 6 interview-guide questions **per expert**, grounded in the transcript,
- surfaces the **exact quote** and **timestamp** behind every answer,
- synthesises **common themes and disagreements** across all 3 experts, and
- lets you **ask free-form questions** across all transcripts.

## Architecture

```
frontend/ (Next.js + Tailwind)  ──HTTP──►  backend/ (FastAPI)  ──►  LLM provider (pluggable)
     3 tabs: Expert Q&A,                     transcript parsing,        anthropic (default):
     Themes & Disagreements,                 timestamp mapping,          native Citations API
     Ask a Question                          quote verification,       groq / huggingface:
                                              retries, disk cache         OpenAI-compatible,
                                                                          open-weight models
```

**Provider is pluggable, not hard-coded** (`app/providers/`, selected via `LLM_PROVIDER`):
- **`anthropic`** (default, production path) — `claude-sonnet-5` via Anthropic's native **Citations** feature. Citations are computed by the API against the literal document text, not generated freeform, so a cited quote cannot be a paraphrase or an invention.
- **`groq`** / **`huggingface`** — OpenAI-compatible endpoints serving open-weight models (e.g. `openai/gpt-oss-120b`). Used for the eval harness and fast local dev iteration, where Anthropic's tighter per-minute rate limits slow down bulk testing. **Tradeoff, stated plainly:** these have no native citation feature, so grounding is enforced entirely by us — the model returns quotes as structured JSON, and we verify each one with a literal substring search against the source transcript before ever showing it. A quote that isn't found verbatim is dropped, never shown. This is a weaker guarantee than Anthropic's API-level offsets (a claim can lose its citation) but it can never fabricate one.

Every provider implementation returns the same shape (`AskResult` / `RawCitation`), so `main.py`'s citation→timestamp resolution and quote-verification guardrail run identically regardless of which one answered.

**How citations/timestamps work (Anthropic path):** each transcript is sent as a `document` content block with citations enabled. The API returns a `cited_text` string plus a character offset into that exact document. The backend never reformats the transcript before sending it, so the offset stays valid, and `transcript_parser.py` walks the transcript's parsed timestamp markers to find the nearest one at-or-before that offset.

**How hallucinations are reduced:**
1. Every answer is generated only from the transcript(s) passed in that request — no outside knowledge, enforced via a system prompt on every provider.
2. Every quote shown in the UI is either an API-computed citation span (Anthropic) or a verbatim-verified substring (Groq/HF) — never a model's free-text description of a quote.
3. A guardrail in `main.py` (`verify_quote`) re-checks every citation against the source transcript regardless of provider before it's ever returned to the client; anything that fails is dropped.
4. If a question isn't addressed in a transcript, every provider is instructed to say so explicitly rather than guess.
5. An **eval harness** (`backend/evals/`) includes "trap" questions the transcripts deliberately don't answer, specifically to regression-test that the pipeline refuses instead of fabricating — see below.

**Why no vector DB at this scale:** with 3 short transcripts, the full text fits comfortably in context, and passing the complete transcript to the grounding mechanism is more accurate than chunk-based retrieval (no risk of the right paragraph being split out of a chunk).

## Scaling from 3 → 30+ transcripts

- **Ingestion:** move from hardcoded expert metadata (`experts.py`) to a manifest/DB row created at upload time.
- **Retrieval:** chunk transcripts by speaker turn, generate contextual embeddings per chunk (prepending a short LLM-written context blurb before embedding — Anthropic's Contextual Retrieval pattern), store in a vector DB (Chroma/pgvector) with hybrid (BM25 + embedding) search and a rerank step.
- **Per-question answers:** retrieve top-k relevant chunks per question instead of the full transcript, then run the same grounding step against just that subset.
- **Cross-transcript synthesis:** replace the single "all docs in one call" pass with a map-reduce: extract per-expert themes/quotes independently (parallelisable), then a reduce pass clusters and cites across all of them.
- **Cost/latency/rate limits:** this is exactly where the provider abstraction pays off — route the high-volume per-chunk extraction pass to Groq/HF open-weight models (cheap, high throughput) and reserve Anthropic's Citations API for the final answer/synthesis step where exact-offset grounding matters most.

## Production-grade layers in this repo

- **Resilience:** `tenacity`-based retry with exponential backoff + jitter on transient provider errors (rate limits, connection errors, 5xx) in every provider; request timeouts; 4xx errors are never retried.
- **Config:** typed, validated settings (`app/config.py`, `pydantic-settings`) instead of scattered `os.environ.get()` calls — fails fast at startup on bad config.
- **Error handling:** a `ProviderCallError` → HTTP 502 exception handler in `main.py`, so a provider outage returns a clean JSON error instead of a raw 500 stack trace.
- **Observability:** structured JSON logging (`app/logging_config.py`) with per-call latency and token usage for every LLM call, tagged by provider.
- **Testing:** `pytest` suite (`backend/tests/`) — transcript/timestamp parsing, the verbatim-quote guardrail, and full API tests against a mocked provider (no network calls, no API cost). Run with `pytest -q`.
- **Eval harness (AI/ML-specific):** `backend/evals/` — a golden regression set mixing real interview-guide questions (must be grounded) with "trap" questions the transcripts don't cover (must NOT produce a citation). Tracks pass rate, fabricated-citation count, latency, and token usage per provider/model, and writes a timestamped JSON report so runs are comparable over time. Run with `python -m evals.run_eval --compare anthropic groq`.
- **Lint/format/types:** `ruff` (lint + format) and `mypy`, configured in `pyproject.toml`; `eslint` + `tsc --noEmit` on the frontend. All clean as of this commit.
- **Frontend tests:** `vitest` + React Testing Library for `CitationChips` and `ErrorBoundary` (`npm test`); a render-time `ErrorBoundary` isolates a broken panel instead of blanking the page.
- **CI:** `.github/workflows/ci.yml` runs backend lint/type-check/tests and frontend lint/type-check/build on every push and PR.
- **Pre-commit:** `.pre-commit-config.yaml` runs ruff + the backend test suite before each commit (`pre-commit install`).
- **Containers:** `backend/Dockerfile` and `frontend/Dockerfile` (multi-stage, non-root user, healthchecks), plus a root `docker-compose.yml` to run both with `docker compose up`.

## Run locally

**Backend**
```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements-dev.txt   # or requirements.txt for runtime-only
cp .env.example .env          # fill in the key for whichever LLM_PROVIDER you use
uvicorn app.main:app --reload --port 8000
```

**Frontend** (separate terminal)
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The first load of each tab calls the LLM live and caches the result to `backend/app/data/cache/`; add `?refresh=true` to a backend URL (e.g. `/api/themes?refresh=true`) to force recomputation.

**With Docker instead:**
```bash
docker compose up --build
```
(requires `backend/.env` to already exist, per above)

**Tests / lint / eval**
```bash
cd backend && pytest -q && ruff check app/ tests/ evals/ && mypy app/
cd frontend && npm test && npm run lint && npx tsc --noEmit
cd backend && python -m evals.run_eval --compare anthropic groq   # costs real API calls
```

## Repo layout

```
backend/app/
  config.py                typed settings (pydantic-settings)
  logging_config.py        structured JSON logging
  transcript_parser.py     timestamp-aware parsing of the raw .txt transcripts
  interview_guide.py       parses the 6 questions from Interview_Guide.txt
  providers/                pluggable LLM providers behind one `Provider` protocol
    anthropic_provider.py    Citations API + retries (production default)
    openai_compatible_provider.py   Groq/HF (open-weight models) + verbatim-quote verification
  main.py                  FastAPI routes + citation→timestamp resolution + quote verification
backend/tests/             pytest suite, provider mocked — no network calls
backend/evals/             golden-set regression eval — real API calls, run manually
frontend/src/
  app/page.tsx              tab shell
  components/                ExpertQAPanel, ThemesPanel, ChatPanel, CitationChips, ErrorBoundary
```

## Reference material used while building this

Researched via GitHub before implementation (see chat history for full analysis):
- [anthropics/claude-cookbooks](https://github.com/anthropics/claude-cookbooks) — Citations API pattern (`misc/using_citations.ipynb`) and the Contextual Retrieval reference for the scaling section above.
- [anthropics/claude-quickstarts](https://github.com/anthropics/claude-quickstarts) — `customer-support-agent` / `financial-data-analyst` for the chat + cited-sources UI shape.
- [anthropics/claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python) — evaluated as an option for orchestration; not needed at 3-transcript scale, called out in the scaling section as the natural next step for a map-reduce pipeline.
