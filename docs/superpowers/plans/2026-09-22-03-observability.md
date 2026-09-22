# Phase 3: Observability — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the two genuinely missing observability gaps — request correlation IDs and cache hit/miss visibility — and upgrade the LLM-call logging that already exists from logfmt-in-message text to proper structured JSON fields.

**Architecture:** No new logging system, no OpenTelemetry SDK — this phase extends `logging_config.py`'s existing `JSONFormatter`/`extra_fields` mechanism, which the provider files already have access to but don't use.

**Tech Stack:** Python stdlib `logging` (unchanged), `uuid` for request IDs.

**Spec:** `docs/superpowers/specs/2026-09-22-frontend-redesign-design.md` §7c (correlation/request ID + cache logging bullet). Full reasoning, including the correction that token/latency/provider logging already existed and was miscounted as a gap in the initial research pass, in `design/OBSERVABILITY_CHECKLIST.md`.

## Global Constraints

- Depends on Phase 1 being complete (this phase touches `main.py`, which Phase 1 already modified — sequence after it, not in parallel).
- No new dependency — everything here uses Python's stdlib `logging` and `contextvars`.
- Every task ends with `pytest -q`, `ruff check app/ tests/ evals/`, `mypy app/` green.

---

## File Structure

- Modify: `backend/app/logging_config.py` — add a request-ID `contextvar` and inject it into every log record automatically (so call sites don't need to remember to pass it).
- Modify: `backend/app/main.py` — request-ID middleware, cache hit/miss log calls at both `read_cache` sites.
- Modify: `backend/app/providers/anthropic_provider.py`, `backend/app/providers/openai_compatible_provider.py` — add `extra=` to the existing `llm_call` log statements.
- Test: `backend/tests/test_main_api.py`, `backend/tests/test_logging_config.py` (new).

---

### Task 1: Request ID — generated, logged, returned as a header

**Files:**
- Modify: `backend/app/logging_config.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_main_api.py`

**Interfaces:**
- Produces: every response gets an `X-Request-ID` header; every log line emitted during that request's handling includes `"request_id"` in its JSON payload, with no call site needing to pass it explicitly.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_main_api.py`:
```python
def test_response_includes_request_id_header(client):
    res = client.get("/api/health")
    assert "X-Request-ID" in res.headers
    assert len(res.headers["X-Request-ID"]) > 0


def test_each_request_gets_a_different_request_id(client):
    first = client.get("/api/health").headers["X-Request-ID"]
    second = client.get("/api/health").headers["X-Request-ID"]
    assert first != second
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_main_api.py::test_response_includes_request_id_header -v` (or `uv run pytest ...` if Phase 1's uv migration has landed)
Expected: FAIL — no `X-Request-ID` header exists yet.

- [ ] **Step 3: Add a request-ID contextvar and inject it into every log record**

In `backend/app/logging_config.py`, add near the top:
```python
import contextvars

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True
```

In `JSONFormatter.format`, add the request ID to every payload:
```python
        payload: dict[str, Any] = {
            "ts": round(time.time(), 3),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
```

In `configure_logging`, attach the filter to the handler:
```python
    handler.addFilter(RequestIDFilter())
```

- [ ] **Step 4: Add middleware that sets the contextvar and the response header**

In `backend/app/main.py`, add near the other middleware:
```python
import uuid

from .logging_config import request_id_var


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    req_id = str(uuid.uuid4())
    token = request_id_var.set(req_id)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["X-Request-ID"] = req_id
    return response
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_main_api.py -v`
Expected: PASS.

- [ ] **Step 6: Add a focused unit test for the formatter itself**

Create `backend/tests/test_logging_config.py`:
```python
import json
import logging

from app.logging_config import JSONFormatter, RequestIDFilter, request_id_var


def test_json_formatter_includes_request_id_from_contextvar():
    token = request_id_var.set("test-request-id-123")
    try:
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello", (), None)
        RequestIDFilter().filter(record)
        formatted = JSONFormatter().format(record)
        payload = json.loads(formatted)
        assert payload["request_id"] == "test-request-id-123"
        assert payload["message"] == "hello"
    finally:
        request_id_var.reset(token)
```

Run: `.venv/Scripts/python.exe -m pytest tests/test_logging_config.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/logging_config.py backend/app/main.py backend/tests/test_main_api.py backend/tests/test_logging_config.py
git commit -m "feat(backend): server-generated request ID on every response + log line

Genuinely absent before this — nothing generated or logged a request
ID. Server-generated via contextvar (never trusts an inbound header),
attached automatically to every log line during that request's
handling, returned as X-Request-ID. The next real increment on the
structured logging that already existed."
```

---

### Task 2: Cache hit/miss logging

**Files:**
- Modify: `backend/app/main.py` (both `read_cache` call sites — `expert_qa` and `themes`)
- Test: `backend/tests/test_main_api.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: a log line at `INFO` on every `/qa` and `/themes` request, with `extra_fields={"cache_hit": bool, "cache_key": str}`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_main_api.py`, using `caplog` (pytest's built-in log-capture fixture):
```python
import logging


def test_cache_hit_and_miss_are_logged(client, fake_provider, caplog):
    for _ in range(6):
        fake_provider.queue(AskResult(answer_text="answer", raw_citations=[]))

    with caplog.at_level(logging.INFO, logger="app.main"):
        client.get("/api/experts/france/qa")  # miss — nothing cached yet
        client.get("/api/experts/france/qa")  # hit — served from cache

    cache_logs = [r for r in caplog.records if "cache" in r.getMessage()]
    assert any(getattr(r, "extra_fields", {}).get("cache_hit") is False for r in cache_logs)
    assert any(getattr(r, "extra_fields", {}).get("cache_hit") is True for r in cache_logs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_main_api.py::test_cache_hit_and_miss_are_logged -v`
Expected: FAIL — no cache-related log lines exist yet.

- [ ] **Step 3: Add the log calls**

In `backend/app/main.py`'s `expert_qa` (around line 103-141) and `themes` (around line 144-178), wrap the existing `cache.read_cache` calls:

```python
    cache_key = f"qa_{expert_id}"
    if not refresh:
        cached = cache.read_cache(cache_key)
        logger.info(
            "cache_lookup",
            extra={"extra_fields": {"cache_key": cache_key, "cache_hit": cached is not None}},
        )
        if cached:
            return cached
```

Same pattern in `themes`, with `cache_key = "themes"`. (If `refresh=True` skips the lookup entirely, no log line is expected for that request — the test above doesn't cover the `refresh=True` path, and this task doesn't need to add one; `refresh=True` bypassing the cache is existing, already-correct, already-tested behavior.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_main_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_main_api.py
git commit -m "feat(backend): log cache hit/miss on /qa and /themes

Genuinely absent before this — read_cache was called but nothing
logged the outcome. Directly a cost/latency signal: hit means no
Anthropic call, miss means a paid one."
```

---

### Task 3: Promote existing LLM-call logging to structured JSON fields

**Files:**
- Modify: `backend/app/providers/anthropic_provider.py`
- Modify: `backend/app/providers/openai_compatible_provider.py`
- Test: existing provider tests (`backend/tests/test_openai_compatible_provider.py`) — extend, don't duplicate.

**Interfaces:**
- Consumes: nothing new — `latency_ms`, `input_tokens`, `output_tokens` already computed at both call sites (confirmed by reading the files before writing this plan).
- Produces: the same log event, now queryable as JSON fields (`gen_ai.usage.input_tokens` etc.) instead of only as text inside `message`.

- [ ] **Step 1: Read the current log call in `anthropic_provider.py` exactly** (already done while writing this plan — reproduced here so the diff is precise):

```python
        logger.info(
            "llm_call provider=anthropic model=%s latency_ms=%d input_tokens=%d "
            "output_tokens=%d num_docs=%d num_citations=%d",
            self.model,
            latency_ms,
            input_tokens,
            output_tokens,
            len(docs),
            len(citations),
        )
```

- [ ] **Step 2: Replace it with a structured-field version, keeping the human-readable message**

```python
        logger.info(
            "llm_call",
            extra={
                "extra_fields": {
                    "gen_ai.system": "anthropic",
                    "gen_ai.request.model": self.model,
                    "gen_ai.usage.input_tokens": input_tokens,
                    "gen_ai.usage.output_tokens": output_tokens,
                    "latency_ms": latency_ms,
                    "num_docs": len(docs),
                    "num_citations": len(citations),
                }
            },
        )
```

- [ ] **Step 3: Apply the equivalent change in `openai_compatible_provider.py`**, using `self.name` (already the provider name — `"groq"` or `"huggingface"`) in place of the hardcoded `"anthropic"` for `gen_ai.system`.

- [ ] **Step 4: Run the existing provider test suite to confirm no behavior regression**

Run: `.venv/Scripts/python.exe -m pytest tests/test_openai_compatible_provider.py -v`
Expected: PASS — this task changes log *format*, not any return value or control flow, so no existing assertion should need to change. If any test asserted on the old log message text specifically, update that one assertion to check `extra_fields` instead (search first: `grep -n "llm_call" backend/tests/`).

- [ ] **Step 5: Commit**

```bash
git add backend/app/providers/anthropic_provider.py backend/app/providers/openai_compatible_provider.py
git commit -m "refactor(backend): structured JSON fields for existing LLM-call logs

Token/latency/provider data was already logged per call — this was
initially miscounted as a missing feature during the observability
audit, corrected after actually reading the provider files. The real
gap was format: logfmt text embedded in the message field, not
separate queryable JSON keys. Field names follow OpenTelemetry's GenAI
Semantic Conventions (gen_ai.*) so a future real OTel migration is a
relabeling exercise, not a rewrite."
```

---

## Phase 3 Completion Check

Before starting Phase 4:
- [ ] `pytest -q` (or `uv run pytest -q`), `ruff check`, `mypy app/` all clean.
- [ ] Manual check: run the dev server, hit `/api/experts/france/qa` twice, tail the stdout log — confirm both requests show the same shape but different `request_id`, the second shows `"cache_hit": true`, and the underlying `llm_call` log line (from the first, cache-missed request) shows `gen_ai.usage.input_tokens` as a top-level JSON key, not buried in `message` text.
