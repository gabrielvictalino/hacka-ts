"""Publica o catálogo revisado resolvendo cada fonte para um trecho já ingerido.

Uso administrativo: ``python -m app.fatos.curadoria``. A ingestão nunca cria fatos; esta etapa só publica
fatos cujos trechos literais foram encontrados na edição exata revisada. Fatos sem fonte disponível ficam
pendentes e não aparecem em ``/fatos``.
"""

import argparse
import json
import re
from datetime import datetime, time, timezone
from uuid import uuid4

from sqlalchemy import text

from app.contracts import CurationItem, CurationReport
from app.db import get_engine
from app.fatos.catalogo import CATALOG, CURATOR, REVIEWED_ON, CuratedFact, Source

# Serializa execuções concorrentes da curadoria (CLI e API).
_LOCK_KEY = 0x1F_A705_C0_4A_7104


def find_quote(excerpt: str, quote: str) -> str | None:
    """Localiza o trecho ignorando apenas diferenças de espaço e quebra de linha; devolve o texto literal."""
    words = quote.split()
    if not words:
        return None
    match = re.search(r"\s+".join(re.escape(word) for word in words), excerpt)
    return match[0] if match else None


def _resolve_source(connection, topic_id, source: Source):
    passages = (
        connection.execute(
            text("""SELECT p.id, p.excerpt, p.section FROM passages p
            JOIN pages pg ON pg.id=p.page_id
            JOIN document_versions v ON v.id=pg.version_id
            JOIN documents d ON d.id=v.document_id
            WHERE v.topic_id=:topic AND d.code=:code AND v.version=:version AND v.status='ready'
              AND pg.physical_page=:page
            ORDER BY (p.section IS NOT DISTINCT FROM :item) DESC, p.ordinal"""),
            {
                "topic": topic_id,
                "code": source.code,
                "version": source.version,
                "page": source.page,
                "item": source.item,
            },
        )
        .mappings()
        .all()
    )
    label = f"{source.code} v{source.version}, p. {source.page}, item {source.item}"
    if not passages:
        return None, f"{label}: edição ou página não publicada no tema."
    for passage in passages:
        literal = find_quote(passage["excerpt"], source.quote)
        if literal:
            return (passage["id"], literal), None
    return None, f"{label}: trecho revisado não encontrado no texto publicado."


def _resolve(connection, fact: CuratedFact):
    topic_id = connection.execute(text("SELECT id FROM topics WHERE name=:name"), {"name": fact.topic}).scalar()
    if topic_id is None:
        return None, None, f"Tema {fact.topic} não encontrado."
    citations, seen = [], set()
    for source in fact.sources:
        resolved, reason = _resolve_source(connection, topic_id, source)
        if resolved is None:
            return None, None, reason
        # Recortes distintos da mesma passagem são evidências próprias; só o recorte repetido é omitido.
        if resolved not in seen:
            seen.add(resolved)
            citations.append((resolved[0], source.item, resolved[1]))
    return topic_id, citations, None


def publish_catalog(connection, catalog: tuple[CuratedFact, ...] = CATALOG) -> CurationReport:
    connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _LOCK_KEY})
    curated_at = datetime.combine(REVIEWED_ON, time(12), tzinfo=timezone.utc)
    items = []
    for position, fact in enumerate(catalog):
        topic_id, citations, reason = _resolve(connection, fact)
        if citations is None:
            # Nunca mantém publicado um fato cuja fonte revisada deixou de ser verificável.
            connection.execute(text("DELETE FROM curated_facts WHERE curation_key=:key"), {"key": fact.key})
            items.append(CurationItem(key=fact.key, status="pending", reason=reason))
            continue
        fact_id = connection.execute(
            text("""INSERT INTO curated_facts(id, topic_id, category, statement, responsible, conditions,
                curated_by, curated_at, curation_key, attribute, area, value, value_text, unit, starts_on, ends_on,
                tags, position)
            VALUES (:id, :topic_id, :category, :statement, :responsible, :conditions, :curated_by, :curated_at,
                :key, :attribute, :area, :value, :value_text, :unit, :starts_on, :ends_on,
                CAST(:tags AS jsonb), :position)
            ON CONFLICT (curation_key) WHERE curation_key IS NOT NULL DO UPDATE SET
                topic_id=EXCLUDED.topic_id, category=EXCLUDED.category, statement=EXCLUDED.statement,
                responsible=EXCLUDED.responsible, conditions=EXCLUDED.conditions, curated_by=EXCLUDED.curated_by,
                curated_at=EXCLUDED.curated_at, attribute=EXCLUDED.attribute, area=EXCLUDED.area,
                value=EXCLUDED.value, value_text=EXCLUDED.value_text, unit=EXCLUDED.unit,
                starts_on=EXCLUDED.starts_on, ends_on=EXCLUDED.ends_on, tags=EXCLUDED.tags,
                position=EXCLUDED.position
            RETURNING id"""),
            {
                "id": uuid4(),
                "topic_id": topic_id,
                "category": fact.category,
                "statement": fact.statement,
                "responsible": fact.responsible,
                "conditions": fact.conditions,
                "curated_by": CURATOR,
                "curated_at": curated_at,
                "key": fact.key,
                "attribute": fact.attribute,
                "area": fact.area,
                "value": fact.value,
                "value_text": fact.value_text,
                "unit": fact.unit,
                "starts_on": fact.starts_on,
                "ends_on": fact.ends_on,
                "tags": json.dumps(list(fact.tags)),
                "position": position,
            },
        ).scalar_one()
        connection.execute(text("DELETE FROM fact_citations WHERE fact_id=:id"), {"id": fact_id})
        for ordinal, (passage_id, item, quote) in enumerate(citations):
            connection.execute(
                text("""INSERT INTO fact_citations(fact_id, passage_id, item, quote, ordinal)
                    VALUES (:fact, :passage, :item, :quote, :ordinal)"""),
                {"fact": fact_id, "passage": passage_id, "item": item, "quote": quote, "ordinal": ordinal},
            )
        items.append(CurationItem(key=fact.key, status="published"))
    # Chaves retiradas do catálogo deixam de ser apresentadas como curadas nos temas que ele cobre.
    connection.execute(
        text("""DELETE FROM curated_facts f USING topics t WHERE t.id=f.topic_id AND t.name = ANY(:topics)
            AND f.curation_key IS NOT NULL AND NOT (f.curation_key = ANY(:keys))"""),
        {"topics": sorted({fact.topic for fact in catalog}), "keys": [fact.key for fact in catalog]},
    )
    published = sum(item.status == "published" for item in items)
    return CurationReport(published=published, pending=len(items) - published, items=items)


def main():
    parser = argparse.ArgumentParser(description="Publica os fatos revisados de Férias e Inovação.")
    parser.add_argument("--strict", action="store_true", help="Sai com código 1 se algum fato ficar pendente.")
    args = parser.parse_args()
    with get_engine().begin() as connection:
        report = publish_catalog(connection)
    for item in report.items:
        print(json.dumps(item.model_dump(), ensure_ascii=False))
    print(json.dumps({"published": report.published, "pending": report.pending}))
    raise SystemExit(1 if args.strict and report.pending else 0)


if __name__ == "__main__":
    main()
