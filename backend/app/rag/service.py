"""Database adapter for hierarchical hybrid retrieval.

The in-memory retriever is intentionally replaceable: production deployments can
substitute managed BM25/vector/reranker adapters while preserving this evidence
bundle contract and its ACL-first project filter.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Call,
    DocumentVersion,
    Project,
    SourceDocument,
    Turn,
)
from app.models import (
    ParentSection as DbParentSection,
)
from app.models import (
    Passage as DbPassage,
)
from app.observability import tracer
from app.providers.types import DocInput
from app.rag.models import ParentContext, Passage
from app.rag.retrieval import HybridRetriever


@dataclass(frozen=True)
class RAGDocument:
    """LLM-safe retrieved context and immutable source metadata for citation checks."""

    doc: DocInput
    original_text: str
    turn_timestamps: tuple[tuple[int, str], ...]
    evidence_start_char: int = 0

    def timestamp_for_offset(self, offset: int) -> str:
        timestamp = "00:00"
        for start_char, candidate in self.turn_timestamps:
            if start_char > offset:
                break
            timestamp = candidate
        return timestamp


@dataclass(frozen=True)
class ContextSelection:
    documents: list[RAGDocument]
    used_full_corpus_fallback: bool


def project_retriever(
    session: Session,
    *,
    tenant_id: str,
    project_name: str,
) -> HybridRetriever:
    """Build an ACL-scoped retriever from the latest ingested project passages."""
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
    rows = session.execute(
        select(DbPassage, DbParentSection, Call)
        .join(DbParentSection, DbPassage.parent_section_id == DbParentSection.id)
        .join(Call, DbPassage.call_id == Call.id)
        .join(DocumentVersion, Call.document_version_id == DocumentVersion.id)
        .join(SourceDocument, DocumentVersion.source_document_id == SourceDocument.id)
        .where(
            SourceDocument.project_id == project.id,
            DocumentVersion.version_number == latest_version,
        )
    ).all()

    passages: list[Passage] = []
    parents: dict[str, ParentContext] = {}
    timestamps_by_call: dict[str, dict[int, str]] = {}
    for passage, parent, call in rows:
        if call.id not in timestamps_by_call:
            timestamps_by_call[call.id] = dict(
                session.execute(
                    select(Turn.ordinal, Turn.start_timestamp).where(Turn.call_id == call.id)
                )
                .tuples()
                .all()
            )
        timestamps = timestamps_by_call[call.id]
        metadata = {
            "tenant_id": tenant_id,
            "project_id": project.id,
            "market": call.market or "",
            "expert_id": call.expert_id,
            "role": call.role or "",
        }
        passages.append(
            Passage(
                id=passage.id,
                source_id=call.expert_id,
                text=passage.text,
                turn_ids=(),
                start_timestamp=timestamps.get(passage.start_turn_ordinal, "00:00"),
                end_timestamp=timestamps.get(passage.end_turn_ordinal, "00:00"),
                raw_start=passage.start_char,
                raw_end=passage.end_char,
                parent_id=parent.id,
                metadata=metadata,
            )
        )
        parents[parent.id] = ParentContext(
            id=parent.id,
            source_id=call.expert_id,
            text=parent.text,
            passage_ids=tuple(),
            metadata=metadata,
        )

    # Reconstruct parent → passage membership for parent-context expansion.
    parent_passages: dict[str, list[str]] = {parent_id: [] for parent_id in parents}
    for passage in passages:
        if passage.parent_id:
            parent_passages[passage.parent_id].append(passage.id)
    normalized_parents = [
        ParentContext(
            parent.id,
            parent.source_id,
            parent.text,
            tuple(parent_passages[parent.id]),
            parent.metadata,
        )
        for parent in parents.values()
    ]
    return HybridRetriever.in_memory(passages, normalized_parents)


def search_project(
    session: Session,
    *,
    tenant_id: str,
    project_name: str,
    query: str,
    filters: Mapping[str, str] | None = None,
):
    """Run project-scoped hybrid retrieval and return evidence bundles."""
    with tracer(__name__).start_as_current_span("rag.retrieve") as span:
        span.set_attribute("hasamex.project", project_name)
        span.set_attribute("hasamex.filter_count", len(filters or {}))
        results = project_retriever(
            session, tenant_id=tenant_id, project_name=project_name
        ).retrieve(query, filters=filters)
        span.set_attribute("hasamex.evidence_count", len(results))
        return results


def documents_for_evidence(session: Session, bundles: list) -> list[RAGDocument]:
    """Turn selected evidence—not the full corpus—into model input documents."""
    passage_ids = [bundle.passage.id for bundle in bundles]
    if not passage_ids:
        return []
    rows = session.execute(
        select(DbPassage.id, Call, DocumentVersion)
        .join(Call, DbPassage.call_id == Call.id)
        .join(DocumentVersion, Call.document_version_id == DocumentVersion.id)
        .where(DbPassage.id.in_(passage_ids))
    ).all()
    sources = {passage_id: (call, version) for passage_id, call, version in rows}
    timestamps_by_call: dict[str, tuple[tuple[int, str], ...]] = {}
    documents: list[RAGDocument] = []
    for bundle in bundles:
        call, version = sources[bundle.passage.id]
        if call.id not in timestamps_by_call:
            timestamps_by_call[call.id] = tuple(
                session.execute(
                    select(Turn.start_char, Turn.start_timestamp)
                    .where(Turn.call_id == call.id)
                    .order_by(Turn.start_char)
                )
                .tuples()
                .all()
            )
        title = " · ".join(part for part in (call.expert_id, call.market) if part)
        documents.append(
            RAGDocument(
                doc=DocInput(
                    expert_id=call.expert_id,
                    title=title or call.expert_id,
                    text=bundle.context,
                ),
                original_text=version.raw_text,
                turn_timestamps=timestamps_by_call[call.id],
                evidence_start_char=bundle.passage.raw_start,
            )
        )
    return documents


def context_for_question(
    session: Session,
    *,
    tenant_id: str,
    project_name: str,
    question: str,
    filters: Mapping[str, str] | None,
    full_corpus_max_characters: int,
) -> ContextSelection:
    """Apply RAG policy before every model call.

    Retrieval is always performed first. Small, permission-filtered corpora may then
    use their complete current source records; large corpora remain evidence-bounded.
    """
    bundles = search_project(
        session,
        tenant_id=tenant_id,
        project_name=project_name,
        query=question,
        filters=filters,
    )
    evidence_documents = documents_for_evidence(session, bundles)
    unique_sources: dict[str, RAGDocument] = {}
    for document in evidence_documents:
        unique_sources.setdefault(document.doc.expert_id, document)
    corpus_size = sum(len(document.original_text) for document in unique_sources.values())
    if corpus_size <= full_corpus_max_characters and unique_sources:
        return ContextSelection(
            documents=[
                RAGDocument(
                    doc=DocInput(
                        expert_id=document.doc.expert_id,
                        title=document.doc.title,
                        text=document.original_text,
                    ),
                    original_text=document.original_text,
                    turn_timestamps=document.turn_timestamps,
                    evidence_start_char=document.evidence_start_char,
                )
                for document in unique_sources.values()
            ],
            used_full_corpus_fallback=True,
        )
    return ContextSelection(documents=evidence_documents, used_full_corpus_fallback=False)
