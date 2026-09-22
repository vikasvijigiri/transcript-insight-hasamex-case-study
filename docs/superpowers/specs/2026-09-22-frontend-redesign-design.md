# Frontend redesign — design spec

**Date:** 2026-09-22
**Status:** approved for planning
**Scope:** `frontend/` visual/UX redesign + `backend/` additions (one new endpoint, one schema field) and hardening (rate limiting, dead-endpoint removal, dependency tooling — §7c). No changes to grounding, citation resolution, or verification logic anywhere.

## 1. Context

The app (Hasamex AI Engineer case study submission) answers questions over 3 expert-call transcripts, with every answer traceable to an exact quote + timestamp. The backend/grounding architecture is complete and correct (Citations API + verbatim-quote guardrail, per `CLAUDE.md`). The frontend is functionally complete but visually generic: default Tailwind utility styling, no design system, no way to see a cited quote in the context of its source transcript.

This spec covers a redesign that makes the citation-grounding guarantee *visible and interactive* — the product's core value prop — rather than changing what the app does.

## 2. Non-goals

- No changes to the *behavior* of `resolve_citations`, `verify_quote`, provider logic, or caching — those are correct and out of scope. (§7b adds one field to `resolve_citations`'s output; it changes what's returned, not how citations are resolved or verified.)
- No new *state management* library (Redux/Zustand/etc. — React state is sufficient at this scale). **Revised after best-practice review**: SWR (a small data-fetching/caching library, not a state manager) is adopted for the panels' fetch logic — see §5. This is a deliberate exception, not a scope-creep reversal: Next.js's own current docs recommend a client cache library for exactly this app's pattern (repeated, click-triggered fetches switching between 3 experts), and it's additive to, not a replacement of, plain React state elsewhere.
- No drag-to-resize panels (see §5 — deliberately cut after research).
- No inline citation markers embedded in answer prose (`[1]`-style). The existing data shape — an answer plus a separate `citations: Citation[]` list — is kept as-is; only its presentation changes.
- No backend auth or deployment/infrastructure changes (reverse proxy, gateway, orchestration — see §12). **Revised after the separate backend best-practices audit**: rate limiting *is* now in scope (§7c) — it was excluded here on the original assumption that backend changes would stay minimal, but the audit found real cost-abuse exposure (unlimited paid Anthropic calls) that outweighs that minimalism. Everything else in this line still holds: no auth system, no deployment topology changes.

## 3. Research grounding

Before designing, three research passes were run (product UX patterns, shadcn/ui technical specifics, open-source reference implementations). Key findings that shaped this spec:

- **NotebookLM, Glean, Notion AI** all use the same pattern for citation click-through: reuse a persistent source panel, scroll to the cited location, highlight it. This is the pattern adopted below, not a novel invention.
- **Perplexity** deliberately shows source identity inline (domain/favicon chips) rather than anonymous `[1]`/`[2]` markers, for trust. This app's existing `CitationChips.tsx` (expert name + quote + timestamp, spelled out) already follows this principle — extended, not replaced.
- **insights-lm-public** (open-source NotebookLM-style app, verified via source) implements exact-span highlighting + `scrollIntoView`-equivalent centering with plain DOM logic — no special library needed for plain-text sources. It also pulled in `react-resizable-panels` (via shadcn's Resizable component) but didn't end up using it, using fixed Tailwind width classes instead. This app follows that lesson: fixed-width panel, no resizable component.
- **shadcn/ui** (current, verified against docs): this repo's Tailwind is already v4 CSS-first (`@theme inline` in `globals.css`), which is exactly what current shadcn init expects — no config-file migration needed. React 19 + npm needs `--legacy-peer-deps` on `shadcn add`/`init` (known peer-dep friction). shadcn's default primitive layer is now Base UI (not Radix) as of July 2026 — but for a deliverable with a hard deadline and no time to debug an unfamiliar, months-old primitive library, this app deliberately opts *out* of the new default and pins **Radix** (`shadcn init -b radix`) instead: years of production hardening, far more prior art if something breaks. "Current default" and "lowest-risk choice under deadline" aren't the same thing, and the latter wins here.

**Post-review amendment (after user pushback on the first draft):** two choices above were revisited and corrected — see §5 (Radix, not Base UI) and §8 (offset-based matching, not `indexOf` alone).

## 4. Information architecture & layout

**Desktop (≥1024px):** a slim full-width top bar (app title, left-aligned; theme toggle button, right-aligned) above a three-column layout that replaces the current top-tab bar.

```
┌──────────────────────────────────────────────────────────────────┐
│  Transcript Insight — Robotic Surgery Market            [☀/🌙]   │
├─────────────┬──────────────────────────┬───────────────────────┤
│  Left rail  │  Center panel             │  Source panel         │
│  (nav)      │  (active view content)    │  (transcript viewer)  │
│             │                            │                       │
│ Ask a       │  Expert Q&A / Themes &     │  Full transcript of   │
│ Question    │  Disagreements / Ask a     │  the expert whose     │
│             │  Question — whichever is   │  citation was last    │
│ Experts:    │  active                    │  clicked (or the      │
│  Dr. Martin │                            │  active expert in     │
│  A. Keller  │                            │  Q&A mode by default) │
│  Dr. Carter │                            │  with the cited quote │
│             │                            │  highlighted + auto-  │
│ Themes &    │                            │  scrolled to it       │
│ Disagree-   │                            │                       │
│ ments       │                            │                       │
└─────────────┴──────────────────────────┴───────────────────────┘
```

- Left rail: fixed width (~240px), replaces the current top-tab nav. Three nav entries: "Expert Q&A" (expands to show the 3 experts as sub-items when active), "Themes & Disagreements", "Ask a Question". Semantic landmarks throughout: `<nav>` for the rail, `<main>` for the center panel — not generic `<div>`s. A visually-hidden "skip to content" link is the first focusable element on the page (WCAG 2.2), jumping past the rail straight to `<main>`.
- Center panel: flexible width, renders whichever view is active — this is where `ExpertQAPanel`/`ThemesPanel`/`ChatPanel`'s content lives, redesigned visually and with their data-fetching migrated to SWR (§5) — the derived-loading-state fix from earlier in this session was the right call at the time and stays conceptually correct, but SWR's own `isLoading`/`error` state makes hand-rolling it unnecessary going forward. One behavior gap fixed as part of this redesign: currently a failed fetch just renders static red text with no way to recover short of reloading the page. Each panel's error state gets a "Try again" button — SWR's `mutate()`/revalidate is the mechanism, replacing what would otherwise have been a manual re-trigger, and lands on the same retry affordance `ErrorBoundary.tsx` already has for render-time crashes.
- Source panel: fixed width (~380px, min 320px), always present on desktop. Default state (nothing clicked yet): shows the transcript of the currently active expert in Q&A mode, or a light placeholder ("Click a citation to see it in its original context") in Themes/Chat mode where no single expert is implied. On citation click (from anywhere — Q&A, Themes, or Chat), it switches to that citation's expert's transcript, scrolls to, and highlights the cited span.
- No drag-to-resize. Fixed widths, per §3's research lesson.

**Mobile/narrow (<1024px):** the top bar persists (title + theme toggle); the left rail collapses into a dropdown/menu beneath it (reusing the same nav entries). Source panel is not a persistent column — clicking a citation opens it as a bottom sheet (shadcn `Sheet`, `side="bottom"`) over the current view, dismissible, showing the same scrolled+highlighted transcript.

**Tablet (768–1024px):** explicitly follows the mobile pattern above, not a third layout. This is called out on purpose: a fixed 380px source panel would crowd the center content at this width, so "persistent column" is reserved for `≥1024px` specifically, and everything below that — tablet included — uses the bottom-sheet behavior. Without this note it would've been easy to build only for "desktop" and "phone" and leave tablet an untested accident.

## 5. Component system

- **shadcn/ui**, initialized fresh via `npx shadcn@latest init -b radix` (with `--legacy-peer-deps` if npm's peer-dep check on React 19 blocks it) — **Radix** primitive layer, not the new Base UI default (see §3), components copied into `frontend/src/components/ui/`.
- Components needed: `button`, `badge` (expert pills, role/market tags), `tooltip` (timestamp/icon affordances), `scroll-area` (source panel, left rail, long answer lists — consistent custom scrollbars), `sheet` (mobile source drawer), `skeleton` (loading states, replacing the current plain-text "Analysing transcript with Claude…" messages). Skeletons must match the loaded content's real dimensions — a differently-sized skeleton is a guaranteed layout shift (CLS) the moment data arrives, not just a visual nitpick.
- The chat question input (currently the one form-like control in the app) gets a real associated `<label>` (visually hidden is fine) — easy to skip on a single-input box, still a WCAG requirement.
- **Folder structure**: `frontend/src/components/` is currently a flat dump (every panel side by side). This redesign adds enough new pieces (left rail, source panel, mobile sheet, several shadcn primitives) that it organizes by feature instead: `components/qa/`, `components/themes/`, `components/chat/`, `components/source-panel/`, `components/layout/` (top bar, left rail), with `components/ui/` reserved for shadcn's own copied-in primitives.
- `frontend/tsconfig.json` gains `noUncheckedIndexedAccess: true` — catches unsafe array/index access (e.g. `citations[i]`, `segments[n]`) by typing the result as possibly `undefined`, the specific strictness flag beyond base `strict` most likely to catch a real bug in exactly this kind of array-heavy rendering code.
- The before/highlighted/after quote split in §8 is built as real React child elements — never `dangerouslySetInnerHTML` with a manually-concatenated string, even though it might look like a shortcut for wrapping a substring in `<mark>`. The codebase has zero uses of it today; this stays true.
- **Data fetching — SWR**: `ExpertQAPanel`, `ThemesPanel`, and `ChatPanel`'s hand-rolled `useEffect`+`fetch`+manual-loading-state pattern is replaced with `useSWR` (keyed by expert id / the fixed themes key / the chat question), per Next.js's own current guidance for click-triggered, repeated client fetches. This gives caching across expert switches (revisiting an expert already viewed doesn't refetch) and built-in loading/error state, which *simplifies* the panels rather than adding complexity on top of them — including `ExpertQAPanel`'s derived-loading-state logic from earlier in this session, which SWR's own `isLoading`/`error` return values make largely redundant. The new `/api/experts/{id}/transcript` endpoint (§7a) is fetched the same way.
- **React Compiler**: enabled via `reactCompiler: true` in `next.config.ts` — stable in Next.js 16, automatic memoization, removes the need to hand-write `useMemo`/`useCallback` for the new components this redesign adds.
- **Not** using shadcn `resizable` (see §3) or `tabs` (replaced by the left rail as primary nav; no remaining use for a tab strip).
- **Theming**: CSS variables in OKLCH (shadcn v4 default), authored as a custom palette (not a shadcn preset) — see §6. `next-themes` added for a light/dark/system toggle button in the header, replacing the current OS-preference-only dark mode. This requires converting `dark:` styling from the current `prefers-color-scheme` media-query default to the `.dark` class strategy (`@custom-variant dark (&:where(.dark, .dark *));` in `globals.css`, which shadcn's init adds automatically).

## 6. Visual direction — "grounded research intelligence"

- **Palette**: neutral zinc/slate base (light + dark), matching the existing app's neutral instinct but formalized as design tokens using the current two-tier convention (W3C Design Tokens Community Group format): *primitive* tokens are the raw color scale (pulled from Radix Colors, §3), *semantic* tokens are purpose-named and reference a primitive (e.g. `--color-citation-accent` → a specific primitive step). Components reference semantic tokens only, never a raw scale value directly — that's what actually survives a re-theme instead of breaking on it. One accent semantic token reserved *exclusively* for citation-related UI (chips, the highlighted span in the source panel, the "verified quote" affordance) so a citation is instantly recognizable anywhere it appears, never reused for unrelated UI (buttons, nav, etc.).
- **Typography**: two-tier scale. UI chrome (nav, labels, buttons) stays compact sans-serif at current sizes. Transcript/quote/answer prose gets a slightly larger size and more line-height than UI chrome — this content is meant to be *read*, not scanned, and the current app treats both identically.
- **Elevation**: soft card elevation (subtle shadow, not just a 1px border) for answer cards and the source panel, replacing the current flat `border-zinc-200` treatment everywhere.
- **Motion**: the current app has zero transitions — every state change is an instant hard cut. CSS-only transitions (no new animation library; Tailwind's built-in `transition`/`duration`/`ease` utilities are sufficient at this scale), restricted to `transform`/`opacity` only (GPU-composited, no layout thrashing — never animate `width`/`height`/`top`/`margin`, which matters here since the source panel and mobile sheet both change size/position): the highlighted quote fades in rather than snapping into existence, the mobile `Sheet` slides in/out (shadcn's default, kept as-is rather than customized), hover/focus states on buttons and citation chips transition rather than jump. Every transition respects `prefers-reduced-motion` (WCAG 2.2) — instant, no animation, when the user has that preference set. Subtle, not decorative — nothing here should add perceptible delay to an interaction.
- **Accessibility numbers, not vibes**: contrast ≥4.5:1 for normal text, ≥3:1 for large text/UI components (WCAG 2.2 AA); interactive touch targets (buttons, citation chips) ≥44×44px, especially on mobile — well above WCAG's 24×24px floor, matching current industry practice; focus rings ≥3:1 contrast against their background and never fully obscured by another element.
- Full token values (hex/oklch, spacing scale, radius) are authored during implementation and recorded in `design/DESIGN_SYSTEM.md` (§9) — this spec fixes the *system*, not exact pixel/color values.

## 7. Backend addition & hardening

Three changes: two additive-only (7a, 7b — zero changes to `resolve_citations`'s or `verify_quote`'s actual logic, just surfacing data those functions already compute but currently discard before it reaches the client), plus a bundle of hardening items from a separate best-practices audit (7c — includes one deletion, dependency tooling, and lightweight middleware).

**7a. New endpoint:**

```
GET /api/experts/{expert_id}/transcript

200 response:
{
  "expert_id": "france",
  "raw_text": "...",
  "segments": [{ "timestamp": "00:04", "start_char": 812 }, ...]
}
404 if expert_id is unknown (same pattern as the existing /qa endpoint)
```

Implementation: reuses `transcript_parser.load_transcript()` and its existing `Transcript`/`Segment` dataclasses — just serializes what's already parsed. Add a `TranscriptResponse` schema to `schemas.py` and one route to `main.py`.

**7b. `Citation` schema gains a `start_char` field:**

```python
class Citation(BaseModel):
    expert_id: str
    expert_name: str
    quote: str
    timestamp: str
    start_char: int  # new — the offset resolve_citations already computed
```

`resolve_citations` in `main.py` already has `rc.start_char_index` in scope when it builds each `Citation` (it's what `timestamp_for_offset` is called with) — currently that value is used once, to derive the timestamp string, and then dropped. Keeping it on the response means the frontend uses the exact location the backend already resolved, instead of re-deriving it via string search (see §8). One field addition, no behavior change to grounding/verification — `verify_quote` still runs exactly as before; this only stops throwing away a number it already has.

Both changes get pytest coverage: the new endpoint's shape/404 behavior, and an assertion that `/qa`, `/themes`, `/chat` responses now include `start_char` on their citations — following the existing test file patterns (no live API calls).

**7c. Backend hardening, from a separate best-practices audit** (full reasoning in `design/BACKEND_BEST_PRACTICES_CHECKLIST.md`) — bundled in here since it's the natural place for backend changes in this pass, distinct from the endpoint/schema additions above:

- **Delete `GET /api/interview-guide`**: confirmed dead (grepped the frontend — never called). OWASP API9 "Improper Inventory Management" territory, not a judgment call.
- **Rate limiting via `slowapi`**: two (soon three, with `/transcript`) endpoints make paid, per-request Anthropic calls with zero limiting today — OWASP API4 "Unrestricted Resource Consumption." Per-IP limits on the Anthropic-calling endpoints specifically, not the whole app; no Redis needed at single-process scale.
- **`TrustedHostMiddleware`**: one line, guards Host-header attacks, cheap given there's no reverse proxy in front doing this already (see §12 for why no reverse proxy is being added).
- **Correlation/request ID + richer log fields**: server-generated request ID (never trust an inbound header), attached to every log line and returned in a response header. Extended with per-request fields on the LLM-calling endpoints specifically: input/output token counts, latency in ms, which provider answered, cache hit/miss, error type if one occurred — named per OpenTelemetry's GenAI Semantic Conventions (`gen_ai.request.model`, `gen_ai.usage.input_tokens`, etc.), not because OTel itself is being adopted now, but so a future real migration to it is a relabeling exercise, not a rewrite. Full reasoning in `design/OBSERVABILITY_CHECKLIST.md`.
- **Gate `/docs`/`/openapi.json`** behind an environment check (`docs_url=None` outside dev) — cheap, stops handing over the full endpoint/schema map for free recon.
- **Dependency management**: migrate `requirements.txt`'s unpinned version ranges to `uv` with a committed lockfile, for reproducible builds. This also means updating `CLAUDE.md`'s documented dev commands (`python -m venv .venv` / `pip install -r requirements-dev.txt` → the `uv` equivalents) as part of the same change, not leaving them stale.
- Explicitly **not** doing, with reasoning (see checklist for full detail): API versioning (`/v1/`, no external consumer to protect), RFC 9457 structured errors (overkill for one consumer), converting sync routes to `async def` (current sync `def` usage is what FastAPI's own docs recommend here), multiple uvicorn workers (Docker Compose already owns replication, don't double-manage it), app-layer security headers (correctly a reverse-proxy concern, and there's no reverse proxy by design — see §12), Sentry/uptime monitoring (nothing to triage without real traffic yet).

These get the same test discipline as everything else: rate-limit behavior and the deleted endpoint's absence covered by pytest, no change to the existing suite's no-live-API-calls constraint.

## 8. Citation → source highlight mechanism

Client-side, on citation click:

1. Fetch (or reuse cached) `/api/experts/{citation.expert_id}/transcript`.
2. Use `citation.start_char` (§7b) directly as the match position — this is the exact offset the backend already resolved from the model's own citation, not a re-derived guess. Compute the match range as `[start_char, start_char + citation.quote.length)`.
   - Fallback only: if `raw_text.slice(start_char, start_char + quote.length) !== quote` (defensive check — should never trigger given `verify_quote`'s guarantee, but cheap to assert), fall back to `raw_text.indexOf(citation.quote)`. This guards against drift between the two values without ever being the primary path, and avoids the silent-wrong-occurrence risk a bare `indexOf` would have if the same phrase appears twice in a transcript.
3. Render the transcript as a sequence of timestamped blocks (using `segments`), splitting the block containing the match into before/highlighted/after spans; the highlighted span wraps in `<mark>` with a ref.
4. `ref.current.scrollIntoView({ behavior: "smooth", block: "center" })` inside the source panel's `ScrollArea` viewport.
5. If `scrollIntoView` proves unreliable inside shadcn's `ScrollArea` viewport during implementation (a documented risk — the reference implementation used manual `offsetTop` math instead, likely for this reason), fall back to manual offset calculation against the viewport's scroll container. Try `scrollIntoView` first; this fallback is not required unless it's observed to misbehave.

## 9. Design audit deliverable

A `design/` folder at the repo root (sibling to `backend/`/`frontend/`):

- `design/DESIGN_SYSTEM.md` — color tokens (light + dark, with hex/oklch values, documented at both the primitive and semantic tier per §6), type scale, spacing scale, and a **component inventory table**: every button/chip/panel/badge variant, which file it's defined in, where it's used, and an approximate instance count across the app.
- `design/screenshots/` — PNGs captured live via Playwright against the running app (not mocked), covering:
  - Expert Q&A: empty/loading (skeleton), loaded with a citation highlighted in the source panel, error state (with the new retry button), error state after clicking retry
  - Themes & Disagreements: loaded, error state
  - Ask a Question: empty, with an answer + citation shown
  - Source panel: default placeholder state, active highlighted state
  - Breakpoints: desktop (≥1024px), tablet (768–1024px, source panel as bottom sheet), mobile (<768px, collapsed nav)
  - Light and dark theme, for at least the Expert Q&A screen
  - Edge-case content, not just the clean example data: a long expert answer, an answer with no citations (the existing "No direct quote found" state in `CitationChips.tsx`), and a long quote in the source panel to confirm the highlight/scroll still centers correctly when the cited span is large

This substitutes for Figma/Penpot, which aren't connected in this environment (Figma needs an OAuth grant via claude.ai connector settings; no Penpot MCP is configured). If the user later connects one, this folder's content (especially the token table) is the source material to port over — nothing here is wasted by that.

## 10. Testing

- New/changed frontend components get Vitest coverage following the existing pattern (`CitationChips.test.tsx`, `ErrorBoundary.test.tsx`): render + key interaction (e.g. clicking a citation triggers the expected callback), not exhaustive visual testing.
- New backend endpoint gets a pytest case in `tests/test_main_api.py`'s style (or a new `test_transcript_endpoint.py`), asserting shape and 404 behavior — no live API calls, consistent with the rest of the suite.
- Visual verification is the Playwright screenshot pass in §9 itself, checked against this spec's layout description before considering the redesign done.
- **Accessibility**: choosing Radix primitives (§5) gives good defaults, but that's an assumption until checked, not a guarantee. Two checks, both via Playwright: (1) `@axe-core/playwright` run against each screen in §9's list, flagging any automated-detectable violation (contrast, missing labels, ARIA misuse); (2) a manual keyboard-only walkthrough — tab through the left rail, a citation chip, and the source panel/mobile sheet, confirming focus is always visible and nothing is a mouse-only trap.
- **Performance**: a single Lighthouse pass (Chrome DevTools or `npx lighthouse`) against the built (`next build && next start`) app before considering the redesign done — not a CI gate, just a sanity check. Concrete bar, not a vague one: **LCP ≤2.5s, INP ≤200ms, CLS ≤0.1** (web.dev's current "good" thresholds), measured once pre-redesign for a baseline and once post-redesign for comparison — the goal is meeting these thresholds, not merely "no worse than before" if before was already poor.
- Full existing verification matrix (`pytest`, `ruff`, `mypy`, `vitest`, `tsc`, `eslint`, `next build`) must stay green throughout — this is a redesign, not a rewrite; nothing here should regress the working grounding/citation logic.
- **Sequencing for the redesign specifically** (full reasoning in `design/TESTING_QA_CHECKLIST.md`): freeze the existing functional/citation-correctness pytest assertions *before* touching any UI and keep them running unchanged throughout — they check content/data, never pixels, so the redesign is free to change everything visual without them ever needing to change. New Playwright visual baselines (`toHaveScreenshot()`) are captured only *after* the redesign, since pre/post pixel comparison across a full visual overhaul is meaningless by design, not a gap.
- **Automated Playwright E2E suite** (new, not the ad hoc manual screenshotting done during this session): 3-5 critical-path tests, added to CI — switch between expert tabs and see different content, ask a question and see an answer with a citation, click a citation and see the source panel highlight, refresh themes. A handful of tests on the paths that matter, not exhaustive coverage.
- **OpenAPI → TypeScript codegen**: `frontend/src/lib/api.ts`'s types are currently hand-maintained separately from `backend/app/schemas.py` — already a drift risk, and this redesign adds a new endpoint and a new `Citation` field at the same time, exactly when that drift happens silently. `openapi-typescript` generates the frontend types from FastAPI's own `/openapi.json` directly, so a future backend schema change fails the frontend build loudly instead of drifting unnoticed.
- **Citation-accuracy metric in the eval harness** (`backend/evals/`): current RAG-eval practice separates citation/faithfulness accuracy from plain answer-correctness — a response can be textually right while citing the wrong span. Golden cases get an added assertion that at least one citation is present and genuinely supports the claim (not just that it exists verbatim somewhere in the transcript); trap cases get their own rubric (correct-refusal phrasing + zero citations), not the same groundedness check as golden cases, since a naive groundedness scorer would otherwise misclassify a correct refusal as "ungrounded."

## 11. Security & repo hygiene additions

Small, cheap, unrelated to the visual redesign but caught while researching current best practice — bundled in since they're trivial and this is the natural time to add them:

- **Content-Security-Policy header**: added via `next.config.js`'s `headers()` (static approach, not nonce-based — this app has no untrusted inline scripts, so the nonce path's cost of forcing full dynamic rendering isn't worth paying).
- **`.github/dependabot.yml`**: baseline dependency-vulnerability scanning for a public GitHub repo (npm + GitHub Actions ecosystems, weekly schedule) — currently absent entirely.
- **Delete unused starter assets**: `frontend/public/{file,globe,next,vercel,window}.svg` are `create-next-app`'s default placeholder icons, confirmed unreferenced anywhere in the app (checked via grep). Cruft, not a design decision — remove during this pass.
- **`gitleaks` in CI**: supplementary secret scanning beyond GitHub's own native scanning on public repos — cheap, current baseline. Full reasoning in `design/SECURITY_CHECKLIST.md`.
- **`npm ci` (not `npm install`) in the frontend CI job**: enforces the committed lockfile's hashes rather than a loose install; the backend gets the equivalent for free via the `uv.lock` migration already decided (§7c).
- CORS and env-var handling were checked and are already correct (explicit origin allowlist, no wildcard, no `allow_credentials`; `NEXT_PUBLIC_API_BASE` isn't a secret) — no change needed, noted here only so it's clear this was verified, not skipped.
- **Not code — yours to do**: Anthropic's console supports a workspace-level spend limit + alert thresholds (50/75/90%) on the API key this app uses. This is a provider-side backstop against a bug or an app-level rate-limit bypass burning real money, and it can only be set from your own Anthropic account (Settings → Plans & Billing → Spending Limits on platform.claude.com) — not something I can configure on your behalf. Recommended before adding a real key to `backend/.env`.

## 12. Out of scope / explicitly deferred

- Resizable/draggable panels (cut per §3/§5).
- Any change to how citations are generated, resolved, or verified (§7b adds a field to the output shape only).
- Figma/Penpot integration (deferred until the user connects one; §9's folder is the interim substitute).
- Any new backend endpoints beyond §7a's single addition.
- Server-side fetching of the initial expert list (converting `page.tsx`'s server/client boundary). Real current-best-practice win, explicitly declined for this pass: meaningfully more implementation risk than anything else in this spec, for a first-paint gain that's marginal on a same-machine dev/demo setup, against a 3-day deadline.
- `loading.tsx`/`error.tsx` Next.js file conventions and Suspense streaming across panels — both genuinely current best practice, but both are route-segment-based, and this app's 3 tabs are client-side view state within one route, not separate routes. Adopting either would require restructuring tabs into real routes, out of scope for this redesign.
- **Reverse proxy / API gateway** (nginx/Caddy/Traefik) in front of Docker Compose. All three backend-audit research passes converged independently on the same conclusion: this earns its keep once there's a real domain needing TLS, multiple backend replicas, or routing across several services — none of which apply to 1 backend + 1 frontend in Docker Compose. Adding one now would be exactly the premature infrastructure complexity "Choose Boring Technology" and "MonolithFirst" argue against. If this ever becomes a real deployment with a domain, Caddy (near-zero-config automatic HTTPS) is the minimum viable addition — not decided now, just the answer if asked later.
- **API versioning** (`/v1/` prefix) — protects external, decoupled consumers from breaking changes; this API has exactly one consumer (its own frontend, same repo, deployed together). Add if a second independent consumer ever appears.
- **RFC 9457 structured error responses**, **Sentry/uptime monitoring**, **app-layer security headers** — each individually justified in `design/BACKEND_BEST_PRACTICES_CHECKLIST.md`, each deferred for the same shape of reason: real value only once this has multiple consumers, real traffic, or a public deployment topology it doesn't have yet.
- **Dedicated prompt-injection defenses** (OWASP LLM01) — reasoned out, not overlooked: that risk is centered on *indirect* injection through untrusted content the app treats as trustworthy (user-uploaded docs, web-fetched pages). This app's 3 documents are static and developer-bundled, never user-supplied — the vector doesn't exist here. Full reasoning in `design/SECURITY_CHECKLIST.md`.
- **SBOM generation, `security.txt`** — both still enterprise/compliance-scale practices per current sources; a lockfile is already a reasonable SBOM substitute at this size, and `security.txt` implies an ongoing external-triage process this case-study project doesn't have.
- **OpenTelemetry SDK/collector, distributed tracing, metrics dashboards, any frontend error-tracking service** (even a lightweight one) — all solve problems a single-process, no-real-traffic demo app doesn't have yet. Full reasoning, including a deliberately-sought counterbalancing source, in `design/OBSERVABILITY_CHECKLIST.md`.
- **Coverage-percentage CI gating, blanket mutation testing** — current consensus treats hard coverage gates as a gameable vanity metric; mutation testing is recommended only for critical modules (noted as a future option for `resolve_citations`/`verify_quote` specifically, not adopted now). Cloud visual-regression services (Percy/Chromatic) — Playwright's own local snapshot comparison is sufficient at this scale.
