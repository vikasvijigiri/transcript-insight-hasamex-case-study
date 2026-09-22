# Frontend redesign — design spec

**Date:** 2026-09-22
**Status:** approved for planning
**Scope:** `frontend/` visual/UX redesign + one small `backend/` addition. No changes to grounding, citation resolution, or verification logic anywhere.

## 1. Context

The app (Hasamex AI Engineer case study submission) answers questions over 3 expert-call transcripts, with every answer traceable to an exact quote + timestamp. The backend/grounding architecture is complete and correct (Citations API + verbatim-quote guardrail, per `CLAUDE.md`). The frontend is functionally complete but visually generic: default Tailwind utility styling, no design system, no way to see a cited quote in the context of its source transcript.

This spec covers a redesign that makes the citation-grounding guarantee *visible and interactive* — the product's core value prop — rather than changing what the app does.

## 2. Non-goals

- No changes to the *behavior* of `resolve_citations`, `verify_quote`, provider logic, or caching — those are correct and out of scope. (§7b adds one field to `resolve_citations`'s output; it changes what's returned, not how citations are resolved or verified.)
- No new runtime state management library (React state is sufficient at this scale).
- No drag-to-resize panels (see §5 — deliberately cut after research).
- No inline citation markers embedded in answer prose (`[1]`-style). The existing data shape — an answer plus a separate `citations: Citation[]` list — is kept as-is; only its presentation changes.
- No backend auth/rate-limiting/deployment changes.

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

- Left rail: fixed width (~240px), replaces the current top-tab nav. Three nav entries: "Expert Q&A" (expands to show the 3 experts as sub-items when active), "Themes & Disagreements", "Ask a Question".
- Center panel: flexible width, renders whichever view is active — this is where `ExpertQAPanel`/`ThemesPanel`/`ChatPanel`'s content lives, redesigned visually but keeping their existing data-fetching logic (including the derived-loading-state fix already in place in `ExpertQAPanel.tsx`).
- Source panel: fixed width (~380px, min 320px), always present on desktop. Default state (nothing clicked yet): shows the transcript of the currently active expert in Q&A mode, or a light placeholder ("Click a citation to see it in its original context") in Themes/Chat mode where no single expert is implied. On citation click (from anywhere — Q&A, Themes, or Chat), it switches to that citation's expert's transcript, scrolls to, and highlights the cited span.
- No drag-to-resize. Fixed widths, per §3's research lesson.

**Mobile/narrow (<1024px):** the top bar persists (title + theme toggle); the left rail collapses into a dropdown/menu beneath it (reusing the same nav entries). Source panel is not a persistent column — clicking a citation opens it as a bottom sheet (shadcn `Sheet`, `side="bottom"`) over the current view, dismissible, showing the same scrolled+highlighted transcript.

## 5. Component system

- **shadcn/ui**, initialized fresh via `npx shadcn@latest init -b radix` (with `--legacy-peer-deps` if npm's peer-dep check on React 19 blocks it) — **Radix** primitive layer, not the new Base UI default (see §3), components copied into `frontend/src/components/ui/`.
- Components needed: `button`, `badge` (expert pills, role/market tags), `tooltip` (timestamp/icon affordances), `scroll-area` (source panel, left rail, long answer lists — consistent custom scrollbars), `sheet` (mobile source drawer), `skeleton` (loading states, replacing the current plain-text "Analysing transcript with Claude…" messages).
- **Not** using shadcn `resizable` (see §3) or `tabs` (replaced by the left rail as primary nav; no remaining use for a tab strip).
- **Theming**: CSS variables in OKLCH (shadcn v4 default), authored as a custom palette (not a shadcn preset) — see §6. `next-themes` added for a light/dark/system toggle button in the header, replacing the current OS-preference-only dark mode. This requires converting `dark:` styling from the current `prefers-color-scheme` media-query default to the `.dark` class strategy (`@custom-variant dark (&:where(.dark, .dark *));` in `globals.css`, which shadcn's init adds automatically).

## 6. Visual direction — "grounded research intelligence"

- **Palette**: neutral zinc/slate base (light + dark), matching the existing app's neutral instinct but formalized as design tokens. One accent color reserved *exclusively* for citation-related UI (chips, the highlighted span in the source panel, the "verified quote" affordance) so a citation is instantly recognizable anywhere it appears, never reused for unrelated UI (buttons, nav, etc.).
- **Typography**: two-tier scale. UI chrome (nav, labels, buttons) stays compact sans-serif at current sizes. Transcript/quote/answer prose gets a slightly larger size and more line-height than UI chrome — this content is meant to be *read*, not scanned, and the current app treats both identically.
- **Elevation**: soft card elevation (subtle shadow, not just a 1px border) for answer cards and the source panel, replacing the current flat `border-zinc-200` treatment everywhere.
- Full token values (hex/oklch, spacing scale, radius) are authored during implementation and recorded in `design/DESIGN_SYSTEM.md` (§9) — this spec fixes the *system*, not exact pixel/color values.

## 7. Backend addition

Two additive-only changes — still zero changes to `resolve_citations`'s or `verify_quote`'s actual logic, just surfacing data those functions already compute but currently discard before it reaches the client.

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

- `design/DESIGN_SYSTEM.md` — color tokens (light + dark, with hex/oklch values), type scale, spacing scale, and a **component inventory table**: every button/chip/panel/badge variant, which file it's defined in, where it's used, and an approximate instance count across the app.
- `design/screenshots/` — PNGs captured live via Playwright against the running app (not mocked), covering:
  - Expert Q&A: empty/loading (skeleton), loaded with a citation highlighted in the source panel, error state
  - Themes & Disagreements: loaded, error state
  - Ask a Question: empty, with an answer + citation shown
  - Source panel: default placeholder state, active highlighted state
  - Mobile (<1024px): collapsed nav, source panel as bottom sheet
  - Light and dark theme, for at least the Expert Q&A screen

This substitutes for Figma/Penpot, which aren't connected in this environment (Figma needs an OAuth grant via claude.ai connector settings; no Penpot MCP is configured). If the user later connects one, this folder's content (especially the token table) is the source material to port over — nothing here is wasted by that.

## 10. Testing

- New/changed frontend components get Vitest coverage following the existing pattern (`CitationChips.test.tsx`, `ErrorBoundary.test.tsx`): render + key interaction (e.g. clicking a citation triggers the expected callback), not exhaustive visual testing.
- New backend endpoint gets a pytest case in `tests/test_main_api.py`'s style (or a new `test_transcript_endpoint.py`), asserting shape and 404 behavior — no live API calls, consistent with the rest of the suite.
- Visual verification is the Playwright screenshot pass in §9 itself, checked against this spec's layout description before considering the redesign done.
- Full existing verification matrix (`pytest`, `ruff`, `mypy`, `vitest`, `tsc`, `eslint`, `next build`) must stay green throughout — this is a redesign, not a rewrite; nothing here should regress the working grounding/citation logic.

## 11. Out of scope / explicitly deferred

- Resizable/draggable panels (cut per §3/§5).
- Any change to how citations are generated, resolved, or verified (§7b adds a field to the output shape only).
- Figma/Penpot integration (deferred until the user connects one; §9's folder is the interim substitute).
- Any new backend endpoints beyond §7a's single addition.
