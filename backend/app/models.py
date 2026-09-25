"""Canonical, versioned evidence entities for the production RAG pipeline."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class IdMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Project(IdMixin, Base):
    __tablename__ = "projects"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, default="local")
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_project_tenant_name"),)


class SourceDocument(IdMixin, Base):
    __tablename__ = "source_documents"
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    external_key: Mapped[str] = mapped_column(String(512), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False, default="text/plain")
    __table_args__ = (
        UniqueConstraint("project_id", "external_key", name="uq_source_project_external"),
    )


class DocumentVersion(IdMixin, Base):
    __tablename__ = "document_versions"
    source_document_id: Mapped[str] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        UniqueConstraint("source_document_id", "version_number", name="uq_document_version_number"),
        UniqueConstraint("source_document_id", "content_hash", name="uq_document_version_hash"),
    )


class Call(IdMixin, Base):
    __tablename__ = "calls"
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    expert_id: Mapped[str] = mapped_column(String(255), nullable=False)
    market: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[str | None] = mapped_column(String(255))


class Speaker(IdMixin, Base):
    __tablename__ = "speakers"
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    __table_args__ = (UniqueConstraint("call_id", "name", name="uq_speaker_call_name"),)


class Turn(IdMixin, Base):
    __tablename__ = "turns"
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    speaker_id: Mapped[str | None] = mapped_column(ForeignKey("speakers.id", ondelete="SET NULL"))
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    start_timestamp: Mapped[str] = mapped_column(String(16), nullable=False, default="00:00")
    end_timestamp: Mapped[str | None] = mapped_column(String(16))
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("call_id", "ordinal", name="uq_turn_call_ordinal"),)


class ParentSection(IdMixin, Base):
    __tablename__ = "parent_sections"
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    start_turn_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    end_turn_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("call_id", "ordinal", name="uq_parent_call_ordinal"),)


class Passage(IdMixin, Base):
    __tablename__ = "passages"
    parent_section_id: Mapped[str] = mapped_column(
        ForeignKey("parent_sections.id", ondelete="CASCADE"), nullable=False
    )
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    start_turn_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    end_turn_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("call_id", "ordinal", name="uq_passage_call_ordinal"),)


class IndexVersion(IdMixin, Base):
    """A versioned retrieval index/chunker/embedding configuration."""

    __tablename__ = "index_versions"
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    chunker_version: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="building")
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_index_project_name"),)


class Embedding(IdMixin, Base):
    """Embeddings are versioned; vector storage can be external or pgvector."""

    __tablename__ = "embeddings"
    passage_id: Mapped[str] = mapped_column(
        ForeignKey("passages.id", ondelete="CASCADE"), nullable=False
    )
    index_version_id: Mapped[str] = mapped_column(
        ForeignKey("index_versions.id", ondelete="CASCADE"), nullable=False
    )
    vector_store_key: Mapped[str] = mapped_column(String(512), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (
        UniqueConstraint("passage_id", "index_version_id", name="uq_embedding_passage_index"),
    )


class CitationSpan(IdMixin, Base):
    __tablename__ = "citation_spans"
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False
    )
    passage_id: Mapped[str | None] = mapped_column(ForeignKey("passages.id", ondelete="SET NULL"))
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    quoted_text: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[str | None] = mapped_column(String(16))


class AnalysisJob(IdMixin, Base):
    __tablename__ = "analysis_jobs"
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    __table_args__ = (
        UniqueConstraint("project_id", "idempotency_key", name="uq_job_project_idempotency"),
    )


class AnalysisCacheEntry(Base):
    """A cached LLM analysis, addressed by the hash of its exact model input.

    Keys carry no tenant: a hit requires the identical source text, so rows are
    safe to share across users, machines, and deploys.
    """

    __tablename__ = "analysis_cache"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


Index("ix_source_documents_project", SourceDocument.project_id)
Index("ix_turns_call_ordinal", Turn.call_id, Turn.ordinal)
Index("ix_passages_call_ordinal", Passage.call_id, Passage.ordinal)
Index("ix_embeddings_index", Embedding.index_version_id)
