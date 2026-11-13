"""Enriquece versões prontas legadas preservando as páginas e citações publicadas."""

from alembic import op
from app.ingestion import backfill_metadata

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    backfill_metadata(op.get_bind())


def downgrade():
    # Metadados corrigidos são dados de negócio e não devem ser apagados na reversão.
    pass
