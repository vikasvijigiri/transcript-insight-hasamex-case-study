"""Small repository layer: keeps SQLAlchemy out of ingestion orchestration."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DocumentVersion, Project, SourceDocument


class EvidenceRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_or_create_project(self, tenant_id: str, name: str) -> Project:
        project = self.session.scalar(
            select(Project).where(Project.tenant_id == tenant_id, Project.name == name)
        )
        if project is None:
            project = Project(tenant_id=tenant_id, name=name)
            self.session.add(project)
            self.session.flush()
        return project

    def get_or_create_source(
        self, project: Project, external_key: str, filename: str
    ) -> SourceDocument:
        source = self.session.scalar(
            select(SourceDocument).where(
                SourceDocument.project_id == project.id, SourceDocument.external_key == external_key
            )
        )
        if source is None:
            source = SourceDocument(
                project_id=project.id, external_key=external_key, filename=filename
            )
            self.session.add(source)
            self.session.flush()
        return source

    def existing_version(self, source: SourceDocument, content_hash: str) -> DocumentVersion | None:
        return self.session.scalar(
            select(DocumentVersion).where(
                DocumentVersion.source_document_id == source.id,
                DocumentVersion.content_hash == content_hash,
            )
        )
