"""Metadados por edição e progresso da ingestão."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE document_versions ADD COLUMN title text;
        ALTER TABLE document_versions ADD COLUMN linked_codes jsonb NOT NULL DEFAULT '[]';
        ALTER TABLE document_versions ADD COLUMN processed_pages integer NOT NULL DEFAULT 0;
        CREATE UNIQUE INDEX ix_ready_document_version ON document_versions(document_id, version)
            WHERE version IS NOT NULL AND status='ready';
    """)


def downgrade():
    op.execute("""
        DROP INDEX ix_ready_document_version;
        ALTER TABLE document_versions DROP COLUMN processed_pages;
        ALTER TABLE document_versions DROP COLUMN linked_codes;
        ALTER TABLE document_versions DROP COLUMN title;
    """)
