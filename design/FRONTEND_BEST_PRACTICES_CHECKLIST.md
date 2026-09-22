# Frontend / UI best-practices checklist

Compiled 2026-09-22 from live research (not memory) against: the [Front-End Checklist](https://github.com/thedaviddias/Front-End-Checklist) project (385 rules across 11 categories), web.dev's Core Web Vitals guidance, WCAG 2.2 (current version — no newer one exists as of this date), current Next.js 16 / React 19 official docs, OWASP CORS guidance, and the W3C Design Tokens Community Group format.

Every item is marked against **this project specifically** — not a generic scorecard. Marking key: ✅ already true (verified against the actual code, not assumed) · 🔧 real gap, folded into the spec as of this pass · ⏭️ deliberately out of scope, with the reason · 🤔 genuine trade-off, needs a decision.

## HTML / document

- ✅ `lang="en"` set on `<html>` (`layout.tsx`)
- ✅ Viewport meta — handled automatically by Next.js App Router's Metadata API
- ✅ Metadata API used (`export const metadata`) — current App Router approach, not legacy `next/head`
- 🔧 Skip-to-content link — missing. Added to spec §4 (implementation plan item).

## CSS

- 🔧 Animation property discipline — the spec's Motion section (§6) said "CSS-only transitions" without constraining *which* properties. Amended to require `transform`/`opacity` only (GPU-composited, no layout thrashing) — never animate `width`/`height`/`top`/`margin`. Directly relevant since the source panel and mobile sheet both change size/position.
- 🔧 `prefers-reduced-motion` — WCAG 2.2 requirement, wasn't in the spec at all. Added: every transition in §6 gets a reduced-motion fallback (instant, no animation).

## JavaScript / TypeScript

- ✅ `strict: true` already set in `tsconfig.json`
- 🔧 `noUncheckedIndexedAccess` — not set. This is the specific flag research flagged as highest-value beyond base `strict`: it catches unsafe array/index access (e.g. `citations[i]`, `segments[n]`) by typing the result as possibly `undefined`. Cheap, real, adds to the spec.
- ✅ No `dangerouslySetInnerHTML` anywhere in the current codebase (verified via grep) — and the new highlight-rendering code (§8) must keep it that way: build the before/highlighted/after split as actual React child elements, never as a manually-concatenated HTML string. Made explicit in the spec so nobody reaches for `dangerouslySetInnerHTML` as a shortcut while building it.

## Performance (Core Web Vitals — current 2026 thresholds)

- 🔧 The spec's Lighthouse check (§10) said "no numeric target, just no regression." Replaced with actual thresholds: **LCP ≤2.5s, INP ≤200ms, CLS ≤0.1** (web.dev's current "good" bar). Concrete target beats a vague one.
- 🔧 CLS specifically: skeleton loading states (§5) must match the real content's dimensions — a skeleton that's a different size than the loaded content is a guaranteed CLS hit the moment data arrives. Added as an explicit constraint.
- ✅ `next/font` already used (self-hosted, no runtime Google Fonts request, no font-swap flash) — already current best practice, no change needed.
- ✅ **React Compiler** — decided: enable it (`reactCompiler: true` in `next.config.ts`). Folded into spec §5.

## Accessibility (WCAG 2.2 Level AA)

- 🔧 Contrast ratios — spec's palette work (§6) gets an explicit requirement: 4.5:1 for normal text, 3:1 for large text/UI components. Not just "looks readable."
- 🔧 Touch targets — WCAG 2.2's new 2.5.8 criterion sets a 24×24px floor; industry practice (and what's being adopted here) is 44×44px for buttons/citation chips, especially on mobile.
- 🔧 Focus visibility — WCAG 2.2's 2.4.11/2.4.13: focus ring must have ≥3:1 contrast against its background and never be fully obscured. Explicit requirement, not left to shadcn's defaults untested (this is exactly what §10's axe-core + keyboard-walkthrough pass already added checks for).
- ✅ Semantic HTML/landmarks — the left rail (`<nav>`), main content (`<main>`) already implied by the layout in §4; made explicit as a requirement rather than assumed.
- ✅ Form labeling — the one form-like control (chat question input) needs a real associated `<label>` (visually hidden is fine) — noted, since it's easy to skip on a single-input chat box.

## Responsive / mobile

- ✅ Breakpoints already chosen (1024/768) land inside the current fluid-first convention (640/768/1024/1280) — no change needed, already reasonably aligned.
- ✅ Viewport meta handled by Next.js automatically, pinch-zoom never disabled (nothing in the codebase sets `user-scalable=no`).

## Security

- 🔧 **Content-Security-Policy header** — currently absent entirely. Next.js 16's static-header approach (`next.config.js` `headers()`) fits this app well: it's not doing anything nonce-sensitive (no untrusted inline scripts), so the static path avoids the cost of forcing full dynamic rendering that the nonce-based approach would impose. Added to the spec as a small, cheap addition.
- 🔧 **Dependency scanning** — no `.github/dependabot.yml` exists. This is the baseline floor for any public GitHub repo per current guidance, and it's a ~10-line YAML file. Added.
- ✅ `NEXT_PUBLIC_API_BASE` is the only public env var and isn't a secret by design — already correct, confirmed earlier in this conversation when adding it to `.gitignore`.
- ✅ Backend CORS already uses an explicit origin allowlist (`CORS_ORIGINS` env var), never a wildcard, and `allow_credentials` isn't set at all (defaults to `False`) — verified in `config.py`/`main.py`. Already matches current OWASP guidance; no change needed.
- ⏭️ Cookie flags (Secure/HttpOnly/SameSite), GDPR cookie consent, privacy policy link — this app sets no cookies and collects no user data. Not applicable.

## Component architecture / design system

- ✅ Choosing Radix (§5) already aligns with current consensus: compound components (Context + hooks) are the standard for stateful multi-part UI, and that's exactly what Radix's primitives are built on.
- 🔧 **Design token structure** — the spec's palette description (§6) was flat ("one accent color for citations"). Formalized to the current two-tier model (W3C Design Tokens Community Group format, stabilized Oct 2025): *primitive* tokens (raw color scale, e.g. from Radix Colors) feed *semantic* tokens (purpose-named, e.g. `--color-citation-accent` referencing a primitive) — components reference only semantic tokens, never raw scale values directly. This is what actually survives a rebrand/retheme; flat raw-value usage doesn't.
- 🔧 **Folder structure** — `frontend/src/components/` is currently a flat dump (all panels + `CitationChips` + `ErrorBoundary` side by side). Current convention for a project this redesign is about to grow (adding a left rail, source panel, mobile sheet, several shadcn primitives) is feature-based colocation, not a bigger flat dump. Added to the spec: new components organize under `components/qa/`, `components/themes/`, `components/chat/`, `components/source-panel/`, `components/layout/`, with `components/ui/` reserved for shadcn's own copied-in primitives.

## Next.js / React-specific (16.3.5 / 19.2)

- ✅ **Client-side data fetching pattern** — decided: adopt SWR, replacing the hand-rolled `useEffect`+`fetch`+manual-state pattern in `ExpertQAPanel`/`ThemesPanel`/`ChatPanel`. §2's non-goal was explicitly revised (not silently reversed) to carve out this one exception. Folded into spec §5.
- ⏭️ **`loading.tsx`/`error.tsx` file conventions** — genuinely current best practice, but they're route-segment-based, and this app's 3 "tabs" are client-side view state within one route, not separate routes. Adopting them would require restructuring tabs into real routes (`/qa`, `/themes`, `/chat`) — a bigger IA change than this redesign's scope. Correctly not adopted, not overlooked.
- ⏭️ **Suspense streaming for independently-loading panels** — the documented benefit is for content that loads *simultaneously*; this app's panels load one at a time (whichever tab is active), so the benefit doesn't apply as described. Not adopted for the same reason as above.
- ⏭️ Server/Client component boundary — every panel is `"use client"` at the top, the anti-pattern Next.js docs call out (mark the leaf, not the whole tree). The main real opportunity — server-side-fetching the initial expert list instead of client-fetching it on mount — was explicitly declined: meaningfully more implementation risk than anything else in this checklist, for a marginal first-paint gain on a same-machine dev/demo setup, against a 3-day deadline. Recorded in spec §12 as a deliberate deferral, not an oversight.
- 🔧 **Unused starter assets** — `frontend/public/{file,globe,next,vercel,window}.svg` are `create-next-app`'s default placeholder icons, unreferenced anywhere in the app. Not a "best practice" item exactly, just cruft found while checking — deleting them during the redesign.
