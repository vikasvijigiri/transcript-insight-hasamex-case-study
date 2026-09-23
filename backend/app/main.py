from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from secrets import compare_digest
from time import perf_counter
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import cache
from .auth import CurrentPrincipal, WritePrincipal
from .config import get_settings
from .database import get_db, get_session_factory, initialize_database
from .experts import EXPERTS, INTERVIEW_GUIDE_FILE, get_expert
from .ingestion import TranscriptIngestionService
from .interview_guide import load_questions
from .logging_config import configure_logging, get_logger
from .models import Call, DocumentVersion, Project, SourceDocument
from .observability import (
    configure_tracing,
    dashboard_snapshot,
    observe_http,
    prometheus_response,
    record_citations,
    record_ingestion,
    record_retrieval,
)
from .providers import DocInput, ProviderCallError, RawCitation, get_provider
from .rag.service import RAGDocument, context_for_question, search_project
from .schemas import (
    ChatRequest,
    ChatResponse,
    Citation,
    ExpertAnswer,
    ExpertQAResponse,
    IngestionResponse,
    IngestTranscriptRequest,
    ObservabilitySnapshot,
    ProjectAskRequest,
    RetrievalRequest,
    RetrievedEvidence,
    SampleCorpusResponse,
    ThemesResponse,
)
from .transcript_parser import load_transcript

# Settings() reads backend/.env itself (via pydantic-settings' env_file config), so no
# explicit load_dotenv() call is needed here.
settings = get_settings()
DatabaseSession = Annotated[Session, Depends(get_db)]
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialize the zero-config local store before accepting requests."""
    if settings.auto_create_schema:
        initialize_database()
    if settings.seed_demo_corpus:
        session = get_session_factory()()
        try:
            ingestion = TranscriptIngestionService(
                session,
                passage_max_tokens=settings.ingestion_passage_max_tokens,
                parent_max_tokens=settings.ingestion_parent_max_tokens,
            )
            for expert in EXPERTS:
                expert_id = str(expert["id"])
                source_file = Path(str(expert["file"]))
                transcript = load_transcript(expert_id, source_file)
                ingestion.ingest_text(
                    tenant_id="local",
                    project_name="Robotics",
                    external_key=f"demo-{expert_id}",
                    filename=str(source_file),
                    expert_id=expert_id,
                    raw_text=transcript.raw_text,
                    market=str(expert["market"]),
                    role=str(expert["role"]),
                )
        finally:
            session.close()
    configure_tracing(settings)
    yield


app = FastAPI(title="Hasamex Transcript Insight API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(observe_http)


@app.middleware("http")
async def request_size_limit(request: Request, call_next):
    """Reject oversized requests before parsing JSON or allocating transcript text."""
    content_length = request.headers.get("content-length")
    try:
        exceeds_limit = (
            content_length is not None and int(content_length) > settings.max_request_bytes
        )
    except ValueError:
        exceeds_limit = True
    if exceeds_limit:
        return JSONResponse(status_code=413, content={"detail": "Request body is too large"})
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Baseline browser protections; TLS/HSTS belongs at the reverse proxy."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.exception_handler(ProviderCallError)
def provider_error_handler(request: Request, exc: ProviderCallError) -> JSONResponse:
    logger.error("Provider call failed on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=502, content={"detail": str(exc)})


QUESTIONS = load_questions(INTERVIEW_GUIDE_FILE)


def verify_quote(quote: str, transcript_raw: str) -> bool:
    """Guardrail applied to every citation regardless of provider: a cited
    span must literally appear in the source transcript we sent, or we drop
    it rather than surface a possibly-mismatched quote. The OpenAI-compatible
    provider (Gemini/Groq/HF) already runs this same check once internally,
    so this is a second, cheap pass."""
    return quote.strip() in transcript_raw


def resolve_citations(raw_citations: list[RawCitation], doc_order: list[dict]) -> list[Citation]:
    resolved: list[Citation] = []
    for rc in raw_citations:
        if rc.document_index >= len(doc_order):
            continue
        expert = doc_order[rc.document_index]
        transcript = load_transcript(expert["id"], expert["file"])
        if not verify_quote(rc.cited_text, transcript.raw_text):
            continue
        resolved.append(
            Citation(
                expert_id=expert["id"],
                expert_name=expert["name"],
                quote=rc.cited_text.strip(),
                timestamp=transcript.timestamp_for_offset(rc.start_char_index),
            )
        )
    record_citations(valid=len(resolved), rejected=len(raw_citations) - len(resolved))
    return resolved


def resolve_rag_citations(
    raw_citations: list[RawCitation], documents: list[RAGDocument]
) -> list[Citation]:
    """Accept citations only if the quote appears in retrieved context and source text."""
    resolved: list[Citation] = []
    for citation in raw_citations:
        if citation.document_index < 0 or citation.document_index >= len(documents):
            continue
        source = documents[citation.document_index]
        quote = citation.cited_text.strip()
        if not quote or quote not in source.doc.text:
            continue
        # Search from the selected evidence region. This avoids assigning a
        # timestamp from an earlier identical phrase elsewhere in the call.
        source_offset = source.original_text.find(quote, source.evidence_start_char)
        if source_offset < 0:
            continue
        resolved.append(
            Citation(
                expert_id=source.doc.expert_id,
                expert_name=_expert_name(source.doc.expert_id),
                quote=quote,
                timestamp=source.timestamp_for_offset(source_offset),
            )
        )
    record_citations(valid=len(resolved), rejected=len(raw_citations) - len(resolved))
    return resolved


def grounded_answer(result, documents: list[RAGDocument]) -> tuple[str, list[Citation]]:
    """Never surface a substantive model answer without verified evidence."""
    answer = result.answer_text.strip()
    citations = resolve_rag_citations(result.raw_citations, documents)
    if answer.casefold().startswith("not addressed"):
        return "Not addressed in the indexed source material.", []
    if not citations:
        return "Not addressed in the indexed source material.", []
    return answer, citations


def _doc_for(expert: dict) -> DocInput:
    transcript = load_transcript(expert["id"], expert["file"])
    return DocInput(
        expert_id=expert["id"],
        title=f"{expert['name']} ({expert['market']})",
        text=transcript.raw_text,
    )


def _expert_name(expert_id: str) -> str:
    """Return bundled case-study names while preserving arbitrary uploaded IDs."""
    try:
        return str(get_expert(expert_id)["name"])
    except KeyError:
        return expert_id


def _project_expert(
    session: Session, *, tenant_id: str, project_name: str, expert_id: str
) -> tuple[Call, DocumentVersion]:
    """Return the latest version of one expert call inside the caller's tenant."""
    project = session.scalar(
        select(Project).where(Project.tenant_id == tenant_id, Project.name == project_name)
    )
    if project is None:
        raise LookupError("Project not found or not accessible")
    latest_version = (
        select(func.max(DocumentVersion.version_number))
        .where(DocumentVersion.source_document_id == SourceDocument.id)
        .correlate(SourceDocument)
        .scalar_subquery()
    )
    result = session.execute(
        select(Call, DocumentVersion)
        .join(DocumentVersion, Call.document_version_id == DocumentVersion.id)
        .join(SourceDocument, DocumentVersion.source_document_id == SourceDocument.id)
        .where(
            SourceDocument.project_id == project.id,
            DocumentVersion.version_number == latest_version,
            Call.expert_id == expert_id,
        )
    ).first()
    if result is None:
        raise LookupError("Expert call not found or not accessible")
    return result.tuple()


def _cache_key(kind: str, tenant_id: str, documents: list[DocInput], prompt_version: str) -> str:
    """Tie cached analysis to the exact corpus and generation configuration."""
    source_fingerprints = [doc.text for doc in documents]
    return cache.build_key(
        kind,
        tenant_id,
        prompt_version,
        settings.llm_provider,
        settings.gemini_model if settings.llm_provider == "gemini" else "",
        settings.groq_model if settings.llm_provider == "groq" else "",
        settings.hf_model if settings.llm_provider == "huggingface" else "",
        *source_fingerprints,
    )


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "authentication_required": settings.auth_required,
    }


@app.get("/api/auth/me")
def current_user(principal: CurrentPrincipal):
    """Small, non-sensitive identity endpoint used to verify deployment auth."""
    return {
        "user_id": principal.user_id,
        "tenant_id": principal.tenant_id,
        "roles": principal.roles,
    }


@app.get("/metrics", include_in_schema=False)
def metrics(request: Request):
    """Prometheus scrape endpoint; never exposes transcript or question content."""
    if settings.metrics_token and not compare_digest(
        request.headers.get("X-Metrics-Token", ""), settings.metrics_token
    ):
        raise HTTPException(401, "Metrics token required")
    return prometheus_response()


@app.get("/api/observability", response_model=ObservabilitySnapshot)
def observability_dashboard(_: CurrentPrincipal):
    """Return browser-safe operational totals for an authenticated workspace user."""
    return dashboard_snapshot()


@app.get("/api/experts")
def list_experts(
    principal: WritePrincipal,
    session: DatabaseSession,
    query: str = "",
    offset: int = 0,
    limit: int = 25,
):
    """List an authenticated project's source profiles in bounded pages."""
    if settings.auth_required:
        if offset < 0 or not 1 <= limit <= 100:
            raise HTTPException(422, "offset must be non-negative and limit must be 1-100")
        project = session.scalar(
            select(Project).where(
                Project.tenant_id == principal.tenant_id, Project.name == "Robotics"
            )
        )
        if project is None:
            return []
        latest_version = (
            select(func.max(DocumentVersion.version_number))
            .where(DocumentVersion.source_document_id == SourceDocument.id)
            .correlate(SourceDocument)
            .scalar_subquery()
        )
        statement = (
            select(Call)
            .join(DocumentVersion, Call.document_version_id == DocumentVersion.id)
            .join(SourceDocument, DocumentVersion.source_document_id == SourceDocument.id)
            .where(
                SourceDocument.project_id == project.id,
                DocumentVersion.version_number == latest_version,
            )
            .order_by(Call.expert_id)
            .offset(offset)
            .limit(limit)
        )
        if query.strip():
            statement = statement.where(Call.expert_id.ilike(f"%{query.strip()}%"))
        return [
            {
                "id": call.expert_id,
                "name": _expert_name(call.expert_id),
                "role": call.role or "Expert call",
                "market": call.market or "Unspecified market",
            }
            for call in session.scalars(statement)
        ]
    return [
        {"id": e["id"], "name": e["name"], "role": e["role"], "market": e["market"]}
        for e in EXPERTS
    ]


@app.get("/api/experts/{expert_id}/transcript")
def expert_transcript(expert_id: str, principal: CurrentPrincipal, session: DatabaseSession):
    """Return the source record exactly as supplied for transparent evidence review."""
    if settings.auth_required:
        try:
            call, version = _project_expert(
                session,
                tenant_id=principal.tenant_id,
                project_name="Robotics",
                expert_id=expert_id,
            )
        except LookupError:
            raise HTTPException(404, "Expert call not found or not accessible") from None
        return {
            "expert_id": call.expert_id,
            "expert_name": _expert_name(call.expert_id),
            "role": call.role or "Expert call",
            "market": call.market or "Unspecified market",
            "raw_text": version.raw_text,
        }
    try:
        expert = get_expert(expert_id)
    except KeyError:
        raise HTTPException(404, f"Unknown expert '{expert_id}'") from None

    transcript = load_transcript(expert_id, expert["file"])
    return {
        "expert_id": expert_id,
        "expert_name": expert["name"],
        "role": expert["role"],
        "market": expert["market"],
        "raw_text": transcript.raw_text,
    }


@app.get("/api/interview-guide")
def interview_guide(principal: CurrentPrincipal):
    return {"questions": QUESTIONS}


@app.post("/api/projects/{project_name}/sources", response_model=IngestionResponse)
def ingest_transcript(
    project_name: str,
    payload: IngestTranscriptRequest,
    session: DatabaseSession,
    principal: CurrentPrincipal,
):
    """Ingest a versioned transcript into the production retrieval corpus.

    The authenticated principal determines the tenant; callers cannot select it.
    """
    result = TranscriptIngestionService(
        session,
        passage_max_tokens=settings.ingestion_passage_max_tokens,
        parent_max_tokens=settings.ingestion_parent_max_tokens,
    ).ingest_text(tenant_id=principal.tenant_id, project_name=project_name, **payload.model_dump())
    record_ingestion(
        project_name,
        created=result.created,
        turns=result.turn_count,
        passages=result.passage_count,
    )
    return IngestionResponse(
        document_version_id=result.document_version.id,
        created=result.created,
        turn_count=result.turn_count,
        passage_count=result.passage_count,
    )


@app.post("/api/projects/{project_name}/sample-corpus", response_model=SampleCorpusResponse)
def import_sample_corpus(
    project_name: str,
    session: DatabaseSession,
    principal: WritePrincipal,
):
    """Import the bundled three-call case study into only the caller's tenant.

    Repeating the request is safe: content-hash ingestion returns existing
    versions instead of duplicating source records.
    """
    ingestion = TranscriptIngestionService(
        session,
        passage_max_tokens=settings.ingestion_passage_max_tokens,
        parent_max_tokens=settings.ingestion_parent_max_tokens,
    )
    imported = 0
    existing = 0
    expert_ids: list[str] = []
    for expert in EXPERTS:
        expert_id = str(expert["id"])
        transcript = load_transcript(expert_id, Path(str(expert["file"])))
        result = ingestion.ingest_text(
            tenant_id=principal.tenant_id,
            project_name=project_name,
            external_key=f"bundled-case-study-{expert_id}",
            filename=Path(str(expert["file"])).name,
            expert_id=expert_id,
            raw_text=transcript.raw_text,
            market=str(expert["market"]),
            role=str(expert["role"]),
        )
        imported += int(result.created)
        existing += int(not result.created)
        expert_ids.append(expert_id)
        record_ingestion(
            project_name,
            created=result.created,
            turns=result.turn_count,
            passages=result.passage_count,
        )
    return SampleCorpusResponse(imported=imported, already_present=existing, expert_ids=expert_ids)


@app.post("/api/projects/{project_name}/retrieve", response_model=list[RetrievedEvidence])
def retrieve_evidence(
    project_name: str,
    payload: RetrievalRequest,
    session: DatabaseSession,
    principal: CurrentPrincipal,
):
    """Return inspectable hybrid-retrieval evidence before any LLM generation."""
    started = perf_counter()
    try:
        bundles = search_project(
            session,
            tenant_id=principal.tenant_id,
            project_name=project_name,
            query=payload.query,
            filters=payload.filters,
        )
    except LookupError:
        raise HTTPException(404, "Project not found or not accessible") from None
    record_retrieval(
        project_name,
        duration_seconds=perf_counter() - started,
        evidence_count=len(bundles),
    )
    return [
        RetrievedEvidence(
            passage_id=bundle.passage.id,
            expert_id=bundle.passage.source_id,
            market=bundle.passage.metadata.get("market") or None,
            start_timestamp=bundle.passage.start_timestamp,
            end_timestamp=bundle.passage.end_timestamp,
            text=bundle.passage.text,
            context=bundle.context,
            score=bundle.retrieval_score,
        )
        for bundle in bundles
    ]


@app.post("/api/projects/{project_name}/ask", response_model=ChatResponse)
def ask_project(
    project_name: str,
    payload: ProjectAskRequest,
    session: DatabaseSession,
    principal: CurrentPrincipal,
):
    """Strict RAG answer path: only retrieved evidence reaches the model."""
    try:
        selection = context_for_question(
            session,
            tenant_id=principal.tenant_id,
            project_name=project_name,
            question=payload.question,
            filters=payload.filters,
            full_corpus_max_characters=settings.rag_full_corpus_max_characters,
        )
    except LookupError:
        raise HTTPException(404, "Project not found or not accessible") from None
    documents = selection.documents
    if not documents:
        return ChatResponse(answer="Not addressed in the indexed source material.", citations=[])
    result = get_provider().ask(
        [document.doc for document in documents],
        (
            f'Question from the research team: "{payload.question}"\n\n'
            "Answer only from the retrieved evidence documents. Do not use prior knowledge or "
            "make inferences beyond the supplied language. If the evidence does not answer the "
            'question, answer exactly: "Not addressed in the indexed source material."'
        ),
        max_tokens=1000,
    )
    answer, citations = grounded_answer(result, documents)
    return ChatResponse(
        answer=answer,
        citations=citations,
        context_mode=(
            "full_transcript_fallback" if selection.used_full_corpus_fallback else "rag_evidence"
        ),
    )


@app.get("/api/experts/{expert_id}/qa", response_model=ExpertQAResponse)
def expert_qa(
    expert_id: str,
    session: DatabaseSession,
    principal: CurrentPrincipal,
    refresh: bool = False,
):
    if settings.auth_required:
        try:
            call, version = _project_expert(
                session,
                tenant_id=principal.tenant_id,
                project_name="Robotics",
                expert_id=expert_id,
            )
        except LookupError:
            raise HTTPException(404, "Expert call not found or not accessible") from None
        expert = {
            "id": call.expert_id,
            "name": _expert_name(call.expert_id),
            "role": call.role or "Expert call",
            "market": call.market or "Unspecified market",
        }
        doc = DocInput(expert_id=call.expert_id, title=expert["name"], text=version.raw_text)
    else:
        try:
            expert = get_expert(expert_id)
        except KeyError:
            raise HTTPException(404, f"Unknown expert '{expert_id}'") from None
        doc = _doc_for(expert)
    cache_key = _cache_key("expert_qa", principal.tenant_id, [doc], "interview-guide-v2-rag")
    if not refresh:
        cached = cache.read_cache(cache_key)
        if cached:
            # Display metadata is resolved at read time so old cached analyses
            # inherit corrected source-profile names without triggering an LLM call.
            cached["expert_name"] = expert["name"]
            return cached

    try:
        selection = context_for_question(
            session,
            tenant_id=principal.tenant_id,
            project_name="Robotics",
            question=" ".join(QUESTIONS),
            filters={"expert_id": expert_id},
            full_corpus_max_characters=settings.rag_full_corpus_max_characters,
        )
    except LookupError:
        selection = None
    if selection is None or not selection.documents:
        return ExpertQAResponse(
            expert_id=expert_id,
            expert_name=expert["name"],
            role=expert["role"],
            market=expert["market"],
            answers=[
                ExpertAnswer(
                    question=question,
                    answer="Not addressed in the indexed source material.",
                    citations=[],
                )
                for question in QUESTIONS
            ],
            context_mode="rag_evidence",
        )
    provider = get_provider()
    prompts = [
        (
            f'Interview-guide question: "{question}"\n\n'
            "Answer this question using ONLY what this expert said in the transcript "
            'document. If it is not addressed, answer exactly: "Not addressed in this '
            'transcript." Otherwise, answer in 1-3 concise sentences, grounded directly '
            "in a specific statement from the transcript."
        )
        for question in QUESTIONS
    ]
    # One call answering all 6 interview-guide questions at once, instead of 6
    # sequential calls — 6 calls per /qa request was enough on its own to exhaust a
    # free-tier requests-per-minute budget (Groq: 30 RPM cap hit in practice).
    results = provider.ask_batch(
        [item.doc for item in selection.documents], prompts, max_tokens=3000
    )
    answers = []
    for question, result in zip(QUESTIONS, results, strict=True):
        answer_text, citations = grounded_answer(result, selection.documents)
        answers.append(ExpertAnswer(question=question, answer=answer_text, citations=citations))

    response = ExpertQAResponse(
        expert_id=expert_id,
        expert_name=expert["name"],
        role=expert["role"],
        market=expert["market"],
        answers=answers,
        context_mode=(
            "full_transcript_fallback" if selection.used_full_corpus_fallback else "rag_evidence"
        ),
    )
    cache.write_cache(cache_key, response.model_dump())
    return response


@app.get("/api/themes", response_model=ThemesResponse)
def themes(session: DatabaseSession, principal: CurrentPrincipal, refresh: bool = False):
    # Demo sources make a safe cache key locally. In production, do not key a
    # tenant's synthesis to static demo files: retrieval must see its newest
    # ingested versions until analysis runs are persisted/versioned in the DB.
    docs = [_doc_for(e) for e in EXPERTS] if not settings.auth_required else []
    cache_key = (
        _cache_key("themes", principal.tenant_id, docs, "market-synthesis-v2-rag") if docs else None
    )
    if cache_key and not refresh:
        cached = cache.read_cache(cache_key)
        if cached:
            return cached

    prompt = (
        "These are 3 expert-call transcripts from the same market-research project on "
        "robotic surgery adoption in Europe (France, Germany, UK). Analyse all three "
        "together and produce exactly two sections:\n\n"
        "COMMON THEMES:\n"
        "A numbered list of 3-5 points where at least two of the three experts clearly "
        "agree.\n\n"
        "DISAGREEMENTS:\n"
        "A numbered list of points where the experts' views differ meaningfully (e.g. on "
        "adoption pace, the weight of ROI/economics vs. training/clinical factors, or "
        "purchase timelines). If there is no genuine disagreement on a topic, do not "
        "invent one.\n\n"
        "Ground every point in what a specific expert actually said."
    )
    try:
        selection = context_for_question(
            session,
            tenant_id=principal.tenant_id,
            project_name="Robotics",
            question=prompt,
            filters=None,
            full_corpus_max_characters=settings.rag_full_corpus_max_characters,
        )
    except LookupError:
        selection = None
    if selection is None or not selection.documents:
        return ThemesResponse(
            common_themes="Not addressed in the indexed source material.",
            disagreements="Not addressed in the indexed source material.",
            citations=[],
            context_mode="rag_evidence",
        )
    result = get_provider().ask([item.doc for item in selection.documents], prompt, max_tokens=1600)
    common, common_citations = grounded_answer(result, selection.documents)

    text = result.answer_text
    common, _, disagree = text.partition("DISAGREEMENTS:")
    common = common.replace("COMMON THEMES:", "").strip()
    disagree = disagree.strip()

    if not common_citations:
        common = "Not addressed in the indexed source material."
        disagree = "Not addressed in the indexed source material."

    response = ThemesResponse(
        common_themes=common,
        disagreements=disagree,
        citations=common_citations,
        context_mode=(
            "full_transcript_fallback" if selection.used_full_corpus_fallback else "rag_evidence"
        ),
    )
    if cache_key:
        cache.write_cache(cache_key, response.model_dump())
    return response


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, session: DatabaseSession, principal: CurrentPrincipal):
    """Legacy route retained for clients; delegates to the same strict RAG policy."""
    return ask_project("Robotics", ProjectAskRequest(question=req.question), session, principal)
