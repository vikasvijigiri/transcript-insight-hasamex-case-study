# Backend best-practices checklist

Compiled 2026-09-22 from live research against: OWASP API Security Top 10 (2023, current version — confirmed no newer API-specific edition exists), Microsoft/Google/Stripe REST API design guides, RFC 9457 (obsoletes RFC 7807), FastAPI's own current official docs, Kubernetes health-check docs (for contrast), 12-Factor App, and current practitioner writing on infrastructure scope (Dan McKinley's "Choose Boring Technology," Martin Fowler's "MonolithFirst"). Cross-checked against the actual backend code, not assumed — `main.py`, `config.py`, `Dockerfile`, `docker-compose.yml`, and `requirements.txt` were all read before drawing conclusions.

Same marking key as the frontend checklist: ✅ already correct (verified) · 🔧 real gap, worth fixing · ⏭️ deliberately out of scope, with the reason · 🤔 genuine trade-off, needs a decision.

## The three questions asked directly

**"How many URLs are required?"** — 6 today, 1 more coming from the frontend redesign spec (§7a, `GET /api/experts/{id}/transcript`), **minus 1 that should be deleted** (`GET /api/interview-guide` — confirmed via grep that the frontend never calls it; OWASP API9 "Improper Inventory Management" is literally about keeping unmonitored, unused endpoints around). Net: **6 endpoints**, all in active use, all resource-nested correctly one level deep (`/experts/{id}/qa`, `/experts/{id}/transcript`) — verified against Microsoft's and Google's REST guides as the textbook-correct pattern, not something to redesign.

| Method | Path | Used by | Verdict |
|---|---|---|---|
| GET | `/api/health` | Docker healthcheck | ✅ keep |
| GET | `/api/experts` | frontend, on load | ✅ keep |
| GET | `/api/interview-guide` | *nobody* | 🔧 delete |
| GET | `/api/experts/{id}/qa` | frontend, per expert click | ✅ keep |
| GET | `/api/themes` | frontend, Themes tab | ✅ keep |
| POST | `/api/chat` | frontend, Ask tab | ✅ keep |
| GET | `/api/experts/{id}/transcript` | frontend redesign, source panel | ✅ add (already specced) |

**"What language to use where?"** — no change, and no polyglot need: Python/FastAPI for the API (already chosen, already well-suited — native Anthropic/OpenAI SDKs, async-capable if ever needed, typed via Pydantic), TypeScript/Next.js for the frontend. There's no database layer, no separate data-processing language need, nothing here that argues for introducing a second backend language. If this were asking "should any part of this move to Go/Rust for performance" — no: the bottleneck in every request is the Anthropic API call (seconds), not Python overhead (microseconds); language choice isn't where performance would come from here.

**"Gateways etc.?"** — the honest answer, backed by all three research passes independently converging on the same conclusion: **not needed at this scale**, and adding one would be the kind of premature infrastructure complexity Dan McKinley's "Choose Boring Technology" and Martin Fowler's "MonolithFirst" specifically argue against. A reverse proxy/gateway (nginx/Caddy/Traefik) earns its keep once there's a real domain needing TLS, multiple backend replicas, or path routing across several services — this is 1 backend + 1 frontend behind Docker Compose, well below where a gateway pays for itself. If this ever becomes a real deployment with a domain, the minimum viable addition would be Caddy (near-zero-config automatic HTTPS) — not Traefik (justified only once routing is dynamic/multi-replica) and not raw nginx (more manual TLS work for no benefit at this scale). Not doing this now, and saying so explicitly is a defensible engineering judgment, not a gap.

## Endpoint/API design

- ✅ URL nesting (`/experts/{id}/qa`) — correct, one level deep, matches Microsoft/Google REST guides' pattern for a true sub-resource. No redesign needed.
- ⏭️ **API versioning** (`/v1/` prefix) — Stripe's own stated philosophy is that versioning protects *external, decoupled* consumers from breaking changes. This app has exactly one consumer (its own frontend, same repo, deployed together) — no source argues a same-repo internal API needs versioning from day one. Add it later only if a second, independent consumer appears.
- ⏭️ **RFC 9457 Problem Details** (structured `application/problem+json` errors) — real, current (obsoletes RFC 7807), used seriously where multiple heterogeneous clients need to branch on error type programmatically. Overkill here: one frontend, already handles FastAPI's default `{"detail": "..."}` shape correctly. Not adopting.
- ✅ Health check — Kubernetes' liveness/readiness split exists for K8s' own reconciliation behavior (restart vs. remove-from-service); Docker Compose's `HEALTHCHECK`/`depends_on: condition: service_healthy` only supports one pass/fail signal, so the split is meaningless here. Current single `/api/health` is already correct, not a gap.
- 🔧 **Gate `/docs`/`/openapi.json` in production** — cheap (`docs_url=None if env=="production" else "/docs"`), nonzero benefit (stops handing over the full endpoint/schema map for free recon). Not urgent since nothing is authenticated yet anyway, but cheap enough to just do.

## FastAPI application layer

- ✅ Single `main.py` — FastAPI's own "Bigger Applications" guide ties splitting into `routers/` to feature/domain growth, not line count; at 194 lines / 6-7 endpoints with two shared helpers, this is well under where splitting pays off. Not restructuring.
- ✅ Sync `def` routes calling blocking SDK calls — FastAPI's own docs are explicit: "when in doubt, use normal def." Sync routes run in Starlette's threadpool automatically, not on the event loop. Correct as-is; converting to `async def` + `AsyncAnthropic` is a legitimate *future* optimization for higher concurrency, not a current defect.
- ✅ Single uvicorn process, no `--workers` — FastAPI's deployment docs are explicit that under an orchestrator (their example: Kubernetes; applies equally to Docker Compose's own container model) you run one process per container and let the platform replicate — adding `--workers` on top double-manages what the platform already owns. Current setup is correct.
- 🔧 **Rate limiting** — the one finding all three research passes converged on independently. Two endpoints make paid, per-request Anthropic calls with zero limiting today; OWASP API4 "Unrestricted Resource Consumption" is exactly this risk. `slowapi` (decorator-based, no Redis needed for a single-process deployment) applied to the Anthropic-calling endpoints specifically (`/qa`, `/themes`, `/chat`, and the eventual repeated hits `/transcript` might get) is the right-sized fix — not gateway-level limiting, which would be the *right* answer only once multiple tenants/apps share a budget.
- 🔧 **`TrustedHostMiddleware`** — one line, guards Host-header attacks, cheap enough to add given there's no reverse proxy in front doing this already.
- 🔧 **Correlation/request ID** — server-generated (never trust an inbound header), attached to every log line and returned in a response header. Cheap, genuinely useful the first time someone reports "it broke" and you need to find the matching log line. The next real increment on top of the structured logging that already exists — not a new observability platform (Sentry/uptime monitoring explicitly deferred below).
- ⏭️ Security headers (CSP, HSTS, X-Content-Type-Options) at the app layer — FastAPI/Starlette ship none of these in core; the maintainers' own position (an unmerged proposal, fastapi/fastapi#8548) is that this belongs at the reverse-proxy/CDN layer. Since this app has no reverse proxy (§ above, deliberately), and isn't being directly internet-exposed for this submission, not adding an in-app headers middleware now — revisit if this ever gets a real public deployment.
- ⏭️ Sentry / uptime monitoring — the value of an error-tracking *service* is triaging errors from real traffic you don't have yet for a case-study demo. Deferred, not forgotten.

## Dependency management

- ✅ **`requirements.txt` version ranges → `uv` + lockfile — decided: migrate.** Real reproducibility gap: `fastapi>=0.115` etc. have no resolver, no lockfile — `pip install` can silently pull different transitive dependency versions across machines/CI runs over time. Current ecosystem consensus (FastAPI's own maintainer projects — Typer, SQLModel, Asyncer — run CI on `uv` as of late 2024) is that `uv` is now the de facto standard, materially faster than Poetry too. This touches the dev commands already documented in `CLAUDE.md` (`python -m venv .venv`, `pip install -r requirements-dev.txt`) — those get updated as part of this change, not left stale.

## 12-Factor / deployment hygiene

- ✅ Config via env vars (Factor III) — already fully followed (`config.py`'s typed `Settings`, `.env.example` pattern).
- ✅ Stateless process (Factor VI) — the on-disk JSON cache is a small, deliberate, documented exception (per-expert/theme Q&A cache, explicitly designed to survive restarts via a Docker volume), not an accidental violation.
- ✅ Logs as event streams (Factor XI) — structured logging already goes to stdout, not files; Docker captures it. Already correct.
- ✅ Dev/prod parity (Factor X) — Docker Compose is 12-Factor's own recommended mechanism for closing this gap; already in place.

## OWASP API Security Top 10 (2023) — applicability, item by item

Of the 10, **7 don't apply** to this app's actual shape (no auth, no database, no per-user objects, no admin roles, no user-supplied URLs to fetch, no endpoint sprawl): API1 (Broken Object-Level Authorization), API2 (Broken Authentication), API3 (Broken Object Property-Level Authorization), API5 (Broken Function-Level Authorization), API7 (SSRF), API9 (Improper Inventory Management — already addressed by deleting the dead endpoint above). **API4 (Unrestricted Resource Consumption) is the one genuine must-check** — addressed by the rate-limiting fix above. API8 (Security Misconfiguration) is generic hygiene worth a glance (CORS already correct, verbose errors already contained by the existing `ProviderCallError` handler). API10 (Unsafe Consumption of APIs) is marginally relevant since this app itself consumes Anthropic's API, but risk is low against a single well-known trusted upstream with timeout/retry already configured (`config.py`'s `request_timeout_seconds`/`max_retries`).
