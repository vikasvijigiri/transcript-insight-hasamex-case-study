# Transcript Insight

**Evidence-first analysis of expert-call transcripts. Every answer is traceable to a verbatim quote and a timestamp.**

Built for the Hasamex AI Engineer case study: three expert calls (France, Germany, UK) on the European robotic-surgery market, analysed against a six-question interview guide.

**Live demo:** https://transcript-insight-hasamex-case-stu.vercel.app
Sign in with Google. The API runs on Render's free tier, so the first request after a period of inactivity can take 30–60 seconds while the instance wakes up.

---

## What it does

| Case requirement | How the app delivers it |
|---|---|
| Upload / read the 3 transcripts | Transcripts are parsed into timestamped speaker turns and ingested into a per-user project corpus |
| Answer the interview guide per expert | **Expert evidence** tab: all 6 questions answered for each expert, side by side with the source transcript |
| Extract exact quotes | Every quote is a verified verbatim substring of the transcript. Paraphrased or invented quotes are discarded, never shown |
| Show source timestamps | Each citation links to the timestamp of the turn it came from, and the quote is highlighted in the full transcript |
| Common themes and disagreements | **Market synthesis** tab: cross-expert themes and explicit disagreements, each backed by citations from the experts involved |
| Ask questions across transcripts | **Ask the corpus** tab: free-form questions answered only from retrieved evidence, with citations |
| Do not invent information | Unsupported questions return *"Not addressed in the indexed source material."*, and this is regression-tested with trap questions |

A fourth tab, **RAG operations**, shows live request, retrieval and citation-validation metrics.

---

## Architecture

```
┌───────────────────────┐      HTTPS + JWT      ┌──────────────────────────────────────────┐
│  Next.js 16 frontend  │ ────────────────────► │  FastAPI backend                         │
│  (Vercel)             │                       │  (Render, Docker)                        │
│                       │                       │                                          │
│  Expert evidence      │                       │  ingestion ─► turn-aware chunking        │
│  Market synthesis     │                       │  retrieval ─► BM25 + vector, RRF fusion, │
│  Ask the corpus       │                       │               rerank, MMR packing        │
│  RAG operations       │                       │  generation ─► pluggable LLM provider    │
└──────────┬────────────┘                       │  grounding ─► verbatim quote check,      │
           │ Google OAuth                       │               offset ─► timestamp        │
           ▼                                    └──────┬─────────────────────┬─────────────┘
   ┌───────────────┐                                   │                     │
   │ Supabase Auth │ ◄──── JWKS verification ──────────┘                     ▼
   └───────────────┘                               PostgreSQL (SQLAlchemy + Alembic)
                                                   Prometheus metrics · OpenTelemetry traces
```

The request path for a question:

1. **Retrieve.** The question is matched against the user's corpus with hybrid search: BM25 plus a vector channel, fused with reciprocal rank fusion, reranked, and packed with MMR so evidence isn't duplicated. When the whole corpus fits within a configurable size (`RAG_FULL_CORPUS_MAX_CHARACTERS`), complete transcripts are sent instead, because with three short calls full context beats chunking.
2. **Generate.** The LLM gets only that evidence, with instructions to answer strictly from it and to return structured JSON containing verbatim quotes.
3. **Ground.** Every quote is located by literal substring search in the exact source text. The resulting character offset, never one reported by the model, is mapped to the nearest timestamp at or before it. Quotes that don't match are dropped.
4. **Verify again.** A final guardrail re-checks each citation against the source before the response leaves the API.

---

## Key design decisions

### Citations and timestamps
Transcripts are parsed into `(timestamp, char_offset)` markers **without modifying the raw text**, so a character offset always means the same thing in the parser, the prompt and the verifier. Timestamps are derived deterministically from where a quote actually appears. The model's claim about where it came from is never used.

### Reducing hallucinations
- **Closed-book generation:** the model sees only retrieved evidence and is told to abstain when the evidence doesn't answer the question.
- **Verbatim-only quotes:** a citation that isn't an exact substring of the source is discarded. A claim can lose its citation, but a citation can never be fabricated.
- **Two independent checks:** grounding at generation time, then a separate verification pass before every response.
- **Explicit abstention:** questions the transcripts don't cover get a fixed "not addressed" answer instead of a guess.
- **Evals with trap questions:** the golden set mixes real interview-guide questions with questions the transcripts deliberately don't answer, and tracks the fabricated-citation count per model.

### Model choice
Providers sit behind one `Provider` protocol and an OpenAI-compatible client, so switching model is a configuration change (`LLM_PROVIDER`), not a code change:

| Provider | Default model | Why |
|---|---|---|
| `groq` *(live deployment)* | `openai/gpt-oss-120b` | Strong instruction-following and reliable JSON output from an open-weight model, with very low latency |
| `gemini` *(local default)* | `gemini-3.6-flash` | Generous free-tier throughput for the multi-call Q&A and synthesis endpoints |
| `huggingface` | `openai/gpt-oss-120b` | Fallback through the Inference Providers router |

None of these offer native citations, so grounding is enforced by the application. That's also why answer quality doesn't depend on any one vendor's features.

### Scaling from 3 to 30+ transcripts
Most of the production path is already in place: persistent ingestion, hybrid retrieval, per-tenant isolation and metadata filters (such as market or expert). To go further:

- **Retrieval:** swap the in-process BM25 and vector adapters for managed ones, e.g. PostgreSQL full-text search plus pgvector with contextual embeddings and a cross-encoder reranker. The retrieval interfaces (`LexicalRetriever`, `VectorRetriever`, `Reranker`) are already defined for this.
- **Synthesis:** move from a single cross-expert call to **map-reduce**: extract themes per transcript in parallel, then cluster and cite them in a reduce pass. Cost grows linearly and each step stays within context limits.
- **Throughput and cost:** answers are cached under content-hashed keys (Redis, or disk locally), LLM concurrency is bounded, and retries use backoff. The high-volume extraction pass can go to a cheaper model while synthesis stays on a stronger one.
- **Ingestion at volume:** an upload queue with background workers, and immutable source versions so citations and evals stay reproducible.

---

## Run locally

**Prerequisites:** Python 3.12+, Node.js 20+, and an API key for one provider (Gemini or Groq; both have free tiers).

Local mode needs no authentication or external database. It uses SQLite and seeds the sample corpus automatically.

```bash
# 1. Backend
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                 # set GEMINI_API_KEY (or LLM_PROVIDER=groq + GROQ_API_KEY)
uvicorn app.main:app --reload --port 8000
```

```bash
# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**. With no Supabase variables set, the frontend skips sign-in and talks to `http://localhost:8000`.

**Or with Docker:** `docker compose up --build` from the repo root (create `backend/.env` first).

---

## Quality

```bash
# Backend: lint, types, tests (provider is mocked, so no network calls or API cost)
cd backend && ruff check app/ tests/ evals/ && mypy app/ && pytest -q

# Frontend: lint, types, unit tests, production build
cd frontend && npm run lint && npx tsc --noEmit && npm test && npm run build

# Model evaluation: real API calls, run manually
cd backend && python -m evals.run_eval --compare gemini groq
```

- **Tests:** a pytest suite covering transcript parsing, chunking, retrieval, grounding, ingestion, caching and the full API against a mocked provider, plus Vitest and Testing Library tests for the key UI components.
- **Evals:** a golden set of grounded and trap questions, reporting pass rate, fabricated citations, latency and token usage per provider. Deterministic retrieval and citation contracts also run inside the normal test suite.
- **CI:** GitHub Actions runs lint, type checks, tests and the frontend build on every push and pull request, and a separate security workflow scans the code and dependencies.

---

## Production

| Concern | Implementation |
|---|---|
| Hosting | Frontend on Vercel, API on Render (Docker, health-checked on `/api/readiness`) |
| Auth | Supabase Auth with Google OAuth. The API verifies JWTs against Supabase JWKS |
| Tenancy | Every corpus, retrieval and answer is scoped to the caller's tenant |
| Data | PostgreSQL through SQLAlchemy, with schema managed by Alembic migrations |
| Security | Strict CORS allow-list, request-size limits, bounded LLM concurrency, CSP and security headers, non-root containers, and startup checks that refuse unsafe production config |
| Resilience | Bounded LLM concurrency, timeouts, and retries with exponential backoff and jitter. Provider failures return a clean 502 |
| Observability | Structured JSON logs, Prometheus `/metrics` (token-protected), OpenTelemetry traces, and a provisioned Grafana dashboard (`ops/`). No transcript text or user data is ever emitted |

---

## Repository layout

```
backend/
  app/
    main.py                  API routes, citation → timestamp resolution, response guardrail
    transcript_parser.py     timestamp-aware parsing that never alters the raw text
    ingestion.py             source ingestion into the evidence store
    rag/                     chunking, hybrid retrieval, grounding (provider-neutral)
    providers/               Provider protocol + OpenAI-compatible implementation
    auth.py                  Supabase JWT verification, tenant and role resolution
    config.py                typed settings with production safety checks
    observability.py         metrics and tracing
    data/                    the 3 transcripts and the interview guide
  migrations/                Alembic schema migrations
  tests/                     pytest suite (mocked provider)
  evals/                     golden-set evaluation harness
frontend/
  src/app/                   page shell and tabs
  src/components/            ExpertQAPanel, ThemesPanel, ChatPanel, CitationChips, AuthGate, ...
ops/                         Prometheus + Grafana provisioning
render.yaml                  Render blueprint for the API
docker-compose.yml           local full stack
```

---

## Limitations and next steps

- The vector channel is a lightweight, dependency-free stand-in. A production deployment would use real embeddings (e.g. pgvector).
- Speaker diarisation comes from the transcript format. Raw audio would need an ASR and diarisation step before ingestion.
- Evals currently cover this corpus. A larger golden set with domain-reviewed reference answers would be the next investment.
