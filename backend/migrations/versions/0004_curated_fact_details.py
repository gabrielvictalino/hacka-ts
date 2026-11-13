"""Atributo, área, valor, unidade e referência literal dos fatos curados."""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE curated_facts ADD COLUMN curation_key text;
        ALTER TABLE curated_facts ADD COLUMN attribute text;
        ALTER TABLE curated_facts ADD COLUMN area text;
        ALTER TABLE curated_facts ADD COLUMN value numeric;
        ALTER TABLE curated_facts ADD COLUMN value_text text;
        ALTER TABLE curated_facts ADD COLUMN unit text;
        ALTER TABLE curated_facts ADD COLUMN starts_on date;
        ALTER TABLE curated_facts ADD COLUMN ends_on date;
        ALTER TABLE curated_facts ADD COLUMN tags jsonb NOT NULL DEFAULT '[]';
        ALTER TABLE curated_facts ADD COLUMN position integer NOT NULL DEFAULT 0;
        ALTER TABLE curated_facts ADD CONSTRAINT ck_curated_facts_period
            CHECK (ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on);
        CREATE UNIQUE INDEX ix_curated_facts_key ON curated_facts(curation_key) WHERE curation_key IS NOT NULL;
        CREATE INDEX ix_curated_facts_filters ON curated_facts(topic_id, category, area);
        ALTER TABLE fact_citations ADD COLUMN item text;
        ALTER TABLE fact_citations ADD COLUMN quote text CHECK (quote IS NULL OR length(quote) > 0);
        ALTER TABLE fact_citations ADD COLUMN ordinal integer NOT NULL DEFAULT 0;
        -- Um fato pode citar recortes distintos da mesma passagem; a ordem identifica cada citação.
        UPDATE fact_citations c SET ordinal=n.ordinal - 1 FROM (
            SELECT fact_id, passage_id, row_number() OVER (PARTITION BY fact_id ORDER BY passage_id) AS ordinal
            FROM fact_citations) n
        WHERE n.fact_id=c.fact_id AND n.passage_id=c.passage_id;
        ALTER TABLE fact_citations DROP CONSTRAINT fact_citations_pkey;
        ALTER TABLE fact_citations ADD CONSTRAINT fact_citations_pkey PRIMARY KEY (fact_id, ordinal);
        CREATE INDEX ix_fact_citations_passage ON fact_citations(passage_id);
    """)


def downgrade():
    op.execute("""
        DROP INDEX ix_fact_citations_passage;
        -- O esquema 0003 aceita uma citação por passagem: mantém o primeiro recorte de cada uma.
        DELETE FROM fact_citations c USING fact_citations f
            WHERE c.fact_id=f.fact_id AND c.passage_id=f.passage_id AND c.ordinal > f.ordinal;
        ALTER TABLE fact_citations DROP CONSTRAINT fact_citations_pkey;
        ALTER TABLE fact_citations ADD CONSTRAINT fact_citations_pkey PRIMARY KEY (fact_id, passage_id);
        ALTER TABLE fact_citations DROP COLUMN ordinal;
        ALTER TABLE fact_citations DROP COLUMN quote;
        ALTER TABLE fact_citations DROP COLUMN item;
        DROP INDEX ix_curated_facts_filters;
        DROP INDEX ix_curated_facts_key;
        ALTER TABLE curated_facts DROP CONSTRAINT ck_curated_facts_period;
        ALTER TABLE curated_facts DROP COLUMN position;
        ALTER TABLE curated_facts DROP COLUMN tags;
        ALTER TABLE curated_facts DROP COLUMN ends_on;
        ALTER TABLE curated_facts DROP COLUMN starts_on;
        ALTER TABLE curated_facts DROP COLUMN unit;
        ALTER TABLE curated_facts DROP COLUMN value_text;
        ALTER TABLE curated_facts DROP COLUMN value;
        ALTER TABLE curated_facts DROP COLUMN area;
        ALTER TABLE curated_facts DROP COLUMN attribute;
        ALTER TABLE curated_facts DROP COLUMN curation_key;
    """)
