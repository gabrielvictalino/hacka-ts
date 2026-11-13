from collections import defaultdict
from uuid import UUID

from sqlalchemy import text

from app.contracts import Citation, CuratedFact, Perspective


def list_facts(
    connection,
    *,
    category: Perspective | None = None,
    topic_id: UUID | None = None,
    area: str | None = None,
    keys: list[str] | None = None,
) -> list[CuratedFact]:
    """Fatos com todas as evidências em versões publicadas; nenhum fato aparece sem citação resolvida."""
    rows = (
        connection.execute(
            text("""SELECT f.id, f.curation_key AS key, f.topic_id, t.name AS topic, f.category, f.attribute,
                f.area, f.statement, f.responsible, f.value, f.value_text, f.unit, f.starts_on, f.ends_on,
                f.conditions, f.tags, f.curated_by, f.curated_at
            FROM curated_facts f JOIN topics t ON t.id=f.topic_id
            WHERE (CAST(:category AS text) IS NULL OR f.category=:category)
              AND (CAST(:topic AS uuid) IS NULL OR f.topic_id=:topic)
              AND (CAST(:area AS text) IS NULL OR lower(f.area)=lower(:area))
              AND (CAST(:keys AS text[]) IS NULL OR f.curation_key = ANY(:keys))
              AND EXISTS (SELECT 1 FROM fact_citations c WHERE c.fact_id=f.id)
              AND NOT EXISTS (
                SELECT 1 FROM fact_citations c
                JOIN passages p ON p.id=c.passage_id JOIN pages pg ON pg.id=p.page_id
                JOIN document_versions v ON v.id=pg.version_id
                WHERE c.fact_id=f.id AND v.status<>'ready')
            ORDER BY t.name, f.category, f.position, f.curated_at, f.id"""),
            {
                "category": category.value if category else None,
                "topic": topic_id,
                "area": area.strip() if area else None,
                "keys": keys,
            },
        )
        .mappings()
        .all()
    )
    if not rows:
        return []
    citations = defaultdict(list)
    for row in connection.execute(
        text("""SELECT c.fact_id, c.passage_id, v.document_id, v.id AS version_id, COALESCE(v.title, d.title) AS title, d.code,
            v.version, pg.physical_page, COALESCE(c.quote, p.excerpt) AS excerpt, COALESCE(c.item, p.section) AS section
        FROM fact_citations c
        JOIN passages p ON p.id=c.passage_id JOIN pages pg ON pg.id=p.page_id
        JOIN document_versions v ON v.id=pg.version_id JOIN documents d ON d.id=v.document_id
        WHERE c.fact_id = ANY(:ids) ORDER BY c.fact_id, c.ordinal, pg.physical_page, p.ordinal"""),
        {"ids": [row["id"] for row in rows]},
    ).mappings():
        citations[row["fact_id"]].append(Citation(**{k: v for k, v in row.items() if k != "fact_id"}))
    return [
        CuratedFact(
            **{**row, "value": float(row["value"]) if row["value"] is not None else None},
            citations=citations[row["id"]],
        )
        for row in rows
    ]


def facts_by_key(connection, keys: list[str]) -> dict[str, CuratedFact]:
    return {fact.key: fact for fact in list_facts(connection, keys=keys) if fact.key}
