"""Temas, documentos, versões, páginas físicas, trechos e fatos curados."""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE topics (
        id uuid PRIMARY KEY, name text NOT NULL UNIQUE
    );
    CREATE TABLE documents (
        id uuid PRIMARY KEY,
        topic_id uuid NOT NULL REFERENCES topics(id),
        title text NOT NULL, code text,
        UNIQUE(topic_id, code)
    );
    CREATE TABLE document_versions (
        id uuid PRIMARY KEY,
        document_id uuid NOT NULL REFERENCES documents(id),
        topic_id uuid NOT NULL REFERENCES topics(id),
        version text, document_type text, document_layer text,
        declared_phase text, valid_from date, valid_until date,
        superseded_by uuid REFERENCES document_versions(id),
        filename text NOT NULL, storage_key text NOT NULL,
        sha256 char(64) NOT NULL,
        status text NOT NULL DEFAULT 'queued'
            CHECK(status IN ('queued', 'processing', 'ready', 'failed')),
        error text, page_count integer CHECK(page_count > 0),
        created_at timestamptz NOT NULL DEFAULT now(),
        processed_at timestamptz,
        UNIQUE(topic_id, sha256),
        CHECK(valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from)
    );
    CREATE INDEX ix_versions_queue ON document_versions(created_at) WHERE status = 'queued';
    CREATE INDEX ix_versions_document ON document_versions(document_id);
    CREATE TABLE pages (
        id uuid PRIMARY KEY,
        version_id uuid NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
        physical_page integer NOT NULL CHECK(physical_page >= 1),
        text text NOT NULL,
        UNIQUE(version_id, physical_page)
    );
    CREATE TABLE passages (
        id uuid PRIMARY KEY,
        page_id uuid NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
        ordinal integer NOT NULL CHECK(ordinal >= 0),
        excerpt text NOT NULL CHECK(length(excerpt) > 0), section text,
        search_vector tsvector GENERATED ALWAYS AS (to_tsvector('portuguese', excerpt)) STORED,
        UNIQUE(page_id, ordinal)
    );
    CREATE INDEX ix_passages_search ON passages USING gin(search_vector);
    CREATE TABLE curated_facts (
        id uuid PRIMARY KEY,
        topic_id uuid NOT NULL REFERENCES topics(id),
        category text NOT NULL CHECK(category IN ('deadline', 'value', 'obligation', 'risk')),
        statement text NOT NULL, responsible text, conditions text,
        curated_by text NOT NULL,
        curated_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE fact_citations (
        fact_id uuid NOT NULL REFERENCES curated_facts(id) ON DELETE CASCADE,
        passage_id uuid NOT NULL REFERENCES passages(id),
        PRIMARY KEY(fact_id, passage_id)
    );
    """)


def downgrade():
    for table in (
        "fact_citations",
        "curated_facts",
        "passages",
        "pages",
        "document_versions",
        "documents",
        "topics",
    ):
        op.execute(f"DROP TABLE {table}")
