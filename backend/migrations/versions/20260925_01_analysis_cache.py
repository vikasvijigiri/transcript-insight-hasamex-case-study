"""Persist the analysis cache in the database so it survives deploys."""

from alembic import op

from app.models import AnalysisCacheEntry

revision = "20260925_01"
down_revision = "20260922_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # checkfirst: fresh databases already get this table from the initial
    # migration's create_all, and the app may have created it lazily.
    AnalysisCacheEntry.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    AnalysisCacheEntry.__table__.drop(op.get_bind(), checkfirst=True)
