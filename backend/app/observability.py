"""Low-cardinality, privacy-safe telemetry for the API and RAG pipeline."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from fastapi import Request, Response
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from app.config import Settings

HTTP_REQUESTS = Counter(
    "hasamex_http_requests_total",
    "Completed HTTP requests.",
    ("method", "route", "status_code"),
)
HTTP_LATENCY = Histogram(
    "hasamex_http_request_duration_seconds",
    "HTTP request duration.",
    ("method", "route"),
)
INGESTED_DOCUMENTS = Counter("hasamex_ingested_documents_total", "New document versions ingested.")
INGESTED_TURNS = Counter("hasamex_ingested_turns_total", "Transcript turns ingested.")
INGESTED_PASSAGES = Counter("hasamex_ingested_passages_total", "RAG passages ingested.")
RETRIEVALS = Counter("hasamex_retrieval_requests_total", "Hybrid retrieval requests.")
RETRIEVAL_LATENCY = Histogram(
    "hasamex_retrieval_duration_seconds", "End-to-end hybrid retrieval duration."
)
RETRIEVED_EVIDENCE = Histogram(
    "hasamex_retrieved_evidence_count", "Evidence bundles returned per retrieval."
)
LLM_REQUESTS = Counter(
    "hasamex_llm_requests_total", "LLM completion attempts.", ("provider", "outcome")
)
LLM_LATENCY = Histogram("hasamex_llm_duration_seconds", "LLM completion latency.", ("provider",))
LLM_TOKENS = Counter("hasamex_llm_tokens_total", "Reported LLM tokens.", ("provider", "direction"))
CITATIONS = Counter("hasamex_citations_total", "Citation verification outcomes.", ("outcome",))
ANALYSIS_CACHE = Counter(
    "hasamex_analysis_cache_total",
    "Analysis cache lookups: hit, coalesced (waited on an identical in-flight request) or miss.",
    ("outcome",),
)
IN_FLIGHT_REQUESTS = Gauge("hasamex_http_requests_in_flight", "Requests currently being served.")


def configure_tracing(settings: Settings) -> None:
    """Configure OTLP only when a collector endpoint is explicitly supplied.

    Trace attributes deliberately contain IDs/counts, never question or transcript text.
    """
    if not settings.otel_exporter_otlp_endpoint:
        return
    provider = TracerProvider(
        resource=Resource.create({"service.name": settings.otel_service_name})
    )
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
    )
    trace.set_tracer_provider(provider)


def tracer(name: str):
    return trace.get_tracer(name)


async def observe_http(request: Request, call_next: Callable[..., Any]) -> Response:
    """Capture route-level request telemetry without high-cardinality URLs."""
    started = time.perf_counter()
    IN_FLIGHT_REQUESTS.inc()
    status_code = 500
    route = "unmatched"
    with tracer(__name__).start_as_current_span("http.request") as span:
        span.set_attribute("http.request.method", request.method)
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            route_object = request.scope.get("route")
            route = getattr(route_object, "path", route)
            duration = time.perf_counter() - started
            HTTP_REQUESTS.labels(request.method, route, str(status_code)).inc()
            HTTP_LATENCY.labels(request.method, route).observe(duration)
            IN_FLIGHT_REQUESTS.dec()
            span.set_attribute("http.route", route)
            span.set_attribute("http.response.status_code", status_code)


def prometheus_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _counter_total(counter: Counter, name: str, labels: dict[str, str] | None = None) -> int:
    """Read a low-cardinality counter without exposing Prometheus text to browsers."""
    return int(
        sum(
            sample.value
            for metric in counter.collect()
            for sample in metric.samples
            if sample.name == name
            and (
                labels is None
                or all(sample.labels.get(key) == value for key, value in labels.items())
            )
        )
    )


def dashboard_snapshot() -> dict[str, int]:
    """Return the safe aggregate values used by the authenticated application UI."""
    return {
        "requests": _counter_total(HTTP_REQUESTS, "hasamex_http_requests_total"),
        "retrievals": _counter_total(RETRIEVALS, "hasamex_retrieval_requests_total"),
        "verifiedCitations": _counter_total(
            CITATIONS, "hasamex_citations_total", {"outcome": "verified"}
        ),
        "rejectedCitations": _counter_total(
            CITATIONS, "hasamex_citations_total", {"outcome": "rejected"}
        ),
        "llmCalls": _counter_total(LLM_REQUESTS, "hasamex_llm_requests_total"),
        "cacheHits": _counter_total(
            ANALYSIS_CACHE, "hasamex_analysis_cache_total", {"outcome": "hit"}
        )
        + _counter_total(ANALYSIS_CACHE, "hasamex_analysis_cache_total", {"outcome": "coalesced"}),
        "cacheMisses": _counter_total(
            ANALYSIS_CACHE, "hasamex_analysis_cache_total", {"outcome": "miss"}
        ),
    }


def record_ingestion(project: str, *, created: bool, turns: int, passages: int) -> None:
    if not created:
        return
    INGESTED_DOCUMENTS.inc()
    INGESTED_TURNS.inc(turns)
    INGESTED_PASSAGES.inc(passages)


def record_retrieval(project: str, *, duration_seconds: float, evidence_count: int) -> None:
    RETRIEVALS.inc()
    RETRIEVAL_LATENCY.observe(duration_seconds)
    RETRIEVED_EVIDENCE.observe(evidence_count)


def record_llm(
    provider: str,
    *,
    outcome: str,
    duration_seconds: float | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    LLM_REQUESTS.labels(provider, outcome).inc()
    if duration_seconds is not None:
        LLM_LATENCY.labels(provider).observe(duration_seconds)
    LLM_TOKENS.labels(provider, "input").inc(input_tokens)
    LLM_TOKENS.labels(provider, "output").inc(output_tokens)


def record_citations(*, valid: int, rejected: int) -> None:
    if valid:
        CITATIONS.labels("verified").inc(valid)
    if rejected:
        CITATIONS.labels("rejected").inc(rejected)


def record_cache(outcome: str) -> None:
    ANALYSIS_CACHE.labels(outcome).inc()
