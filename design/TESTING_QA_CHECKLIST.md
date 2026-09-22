# Testing / QA checklist

Compiled 2026-09-22. Audits the *existing* test strategy against current practice — 16 backend pytest tests (unit-level, provider mocked, no live calls), 5 frontend Vitest tests (component-level), and a separate `evals/` harness (golden/trap cases, real paid API calls, deliberately kept out of CI) — rather than issuing a generic "write more tests" list.

Same marking key: ✅ already correct/adequate · 🔧 real gap, worth fixing · ⏭️ deliberately out of scope, with the reason.

## LLM eval strategy

- ✅ **Golden + trap case shape is correct, not a shortcut.** Anthropic's own eval guidance explicitly warns that testing only "should answer" cases biases a system toward confident hallucination — golden (should-answer) + trap (should-refuse) is the right minimal shape, already what this app's `evals/golden_cases.py` does.
- 🔧 **Citation accuracy isn't scored as its own metric.** Current RAG-eval practice (OpenAI's eval guidance, RAGAS-style groundedness scoring) increasingly separates *faithfulness/citation-accuracy* from plain answer-correctness — a response can be textually right while citing the wrong span. Given this app's entire value proposition is exact-quote traceability, the eval harness should assert, per case: for golden cases, at least one citation is present and its quote genuinely supports the claim (not just that `verify_quote` passed server-side, which only proves the quote exists verbatim somewhere in the transcript, not that it's the *right* quote for this specific claim); for trap cases, the response has zero citations (a correct refusal shouldn't be citing anything). One noted pitfall from research: naive groundedness scorers misclassify correct refusals as "ungrounded" because refusal text isn't a literal quote — trap-case assertions need their own rubric (check for the refusal phrasing + absence of citations), not the same groundedness check as golden cases.

## Test pyramid & automated E2E

- ✅ **Proportion is fine.** 16 backend + 5 frontend unit/component tests with zero E2E is directionally pyramid-shaped (unit-heavy base), not inverted — the gap isn't proportion.
- 🔧 **The real gap: zero automated E2E exists.** Nothing currently exercises FastAPI + Next.js actually talking to each other, and this session's Playwright use has all been manual/ad hoc screenshotting, not a regression-protected suite. Current guidance: a handful of tests on critical paths only (not exhaustive coverage) — for this app that's ~3-5 tests: switch expert tabs and see different content, ask a question and see an answer with a citation, click a citation and see the source panel highlight (once the redesign lands), refresh themes/cache. Added to CI as a smoke-test layer, separate from the unit suites.
- ⏭️ **Coverage-percentage CI gating** — current consensus treats hard coverage-percent gates as a widely-criticized vanity metric (gameable, doesn't measure assertion quality). Not adding one. If a signal beyond "tests pass" is wanted later, targeted mutation testing on the grounding/citation path specifically (`resolve_citations`/`verify_quote`) is the more current recommendation — noted as a future option, not part of this pass.

## Contract safety between frontend and backend

- 🔧 **OpenAPI → TypeScript codegen.** `frontend/src/lib/api.ts`'s types are hand-maintained separately from `backend/app/schemas.py`'s Pydantic models — already a manual-sync risk today, and this redesign adds a new endpoint (`/transcript`) and a new `Citation` field (`start_char`) at the same time, which is exactly when hand-sync drift happens. FastAPI natively exposes `/openapi.json`; a tool like `openapi-typescript` generates the frontend types from it directly, so a future backend schema change fails the frontend build loudly instead of drifting silently. Well-timed to adopt during this redesign rather than after.

## Regression safety net for the redesign specifically

- 🔧 **Sequencing, not just more tests.** Current practice for "big visual redesign on top of working, tested logic": freeze *functional* assertions (citation content/correctness — already what the existing pytest suite checks) before the redesign starts and keep them running unchanged throughout; only pixel-level UI gets new visual baselines (Playwright's built-in `toHaveScreenshot()`, zero extra dependency), captured *after* the redesign, not compared against pre-redesign pixels since those are expected to change completely. The two must stay strictly separate — a visual snapshot test should never be the thing that would catch a broken citation, and a functional test should never fail just because a button moved.

## Explicitly not doing, with reasoning

- ⏭️ Cloud visual-regression services (Percy/Chromatic) — add real value (hosted review workflow, cross-browser rendering farms) but aren't required to get the sequencing benefit above; Playwright's own local snapshot comparison is sufficient at this scale.
- ⏭️ Mutation testing as a blanket practice — current guidance recommends it only for critical modules, not as a general small-project baseline; noted above as a future option for `resolve_citations`/`verify_quote` specifically if ever wanted, not adopted now.
