"""Consulta textual conservadora: afirmações sempre reproduzem evidências do acervo."""

import json
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import text

from app.bedrock import generate_claims
from app.calculations import answer_calculation
from app.config import get_settings
from app.contracts import Citation, Claim, QuestionRequest, QuestionResponse
from app.db import get_engine
from app.question_support import normalize_terms, search_terms, support_assertions
from app.vigencia.situacao import version_states

logger = logging.getLogger(__name__)
# Palavras de formulação da pergunta não são requisitos de evidência.
QUESTION_WORDS = re.compile(
    r"\b(qual|quais|quanto|quantos|quanta|quantas|como|quando|onde|quem|posso|podemos|"
    r"gostaria|saber|preciso|devo|devemos|existe|existem|diga|explique|informe|sobre)\b",
    re.I,
)
PERSPECTIVES = {
    "deadline": "prazo dias antecedência data até",
    "value": "valor reais pagamento custo multa",
    "obligation": "deve deverá obrigatório responsável obrigação",
    "risk": "risco penalidade multa vedado proibido",
}
CITATION_COLUMNS = """v.id AS version_id, v.document_id, s.id AS passage_id,
    COALESCE(v.title, d.title, v.filename) AS title, d.code, v.version,
    p.physical_page, s.excerpt, s.section, v.document_type, v.document_layer,
    v.declared_phase, v.valid_from, v.valid_until"""
CITATION_JOINS = """FROM passages s JOIN pages p ON p.id=s.page_id
    JOIN document_versions v ON v.id=p.version_id JOIN documents d ON d.id=v.document_id"""


def citation_by_id(passage_id):
    # Sem filtro de vigência: uma evidência já apresentada continua histórica e verificável.
    with get_engine().connect() as connection:
        row = (
            connection.execute(
                text(f"SELECT {CITATION_COLUMNS}, p.text AS page_text {CITATION_JOINS} WHERE s.id=:id"),
                {"id": passage_id},
            )
            .mappings()
            .first()
        )
    if not row:
        raise HTTPException(404, "Evidência não encontrada.")
    return verified_citation(row)


def verified_citation(row):
    if " ".join(row["excerpt"].split()) not in " ".join(row["page_text"].split()):
        return None
    return Citation.model_validate({key: row[key] for key in Citation.model_fields})


def eligible_versions(connection, topic_id, reference):
    # A mesma classificação alimenta a consulta e a tela de vigência.
    return [vid for vid, state in version_states(connection, topic_id, reference).items() if state.applicable]


def reference_date(body):
    if body.reference_date:
        return body.reference_date
    found = re.findall(r"\b(?:\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})\b", body.question)
    if len(set(found)) > 1:
        raise HTTPException(422, "Informe reference_date para consultar uma pergunta com várias datas.")
    if found:
        try:
            return datetime.strptime(found[0], "%d/%m/%Y" if "/" in found[0] else "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(422, "Data inválida na pergunta.") from exc
    return datetime.now(ZoneInfo("America/Recife")).date()


def query_terms(value):
    value = re.sub(r"\b(?:\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})\b", " ", value)
    value = QUESTION_WORDS.sub(" ", normalize_terms(value))
    return value.strip(" ?.,;!\n")


def answer(body: QuestionRequest) -> QuestionResponse:
    reference = reference_date(body)
    body = body.model_copy(update={"reference_date": reference})
    if body.calculation is not None:
        return answer_calculation(body, eligible_versions, verified_citation)
    facets = [part.strip(" ?.,;!\n") for part in re.split(r"[?;\n]+|\s+e\s+", body.question) if query_terms(part)]
    if len(facets) > 12:
        raise HTTPException(422, "Divida a consulta em até 12 pontos por pergunta.")
    gaps, citations, confirmed = [], {}, 0
    coverage = []
    with get_engine().connect() as connection:
        if not connection.execute(text("SELECT 1 FROM topics WHERE id=:id"), {"id": body.topic_id}).scalar():
            raise HTTPException(404, "Tema não encontrado.")
        versions = eligible_versions(connection, body.topic_id, reference)
        for facet in facets:
            rows = (
                connection.execute(
                    text(rf"""
                WITH query AS (
                    SELECT replace(plainto_tsquery('portuguese', :search)::text, ' & ', ' | ')::tsquery AS broad_query,
                    replace(plainto_tsquery('portuguese', :perspective)::text, ' & ', ' | ')::tsquery AS perspective
                )
                SELECT {CITATION_COLUMNS}, p.text AS page_text
                {CITATION_JOINS} CROSS JOIN query q
                WHERE v.id = ANY(CAST(:versions AS uuid[])) AND v.status='ready'
                    AND v.topic_id=:topic AND s.search_vector @@ q.broad_query
                    AND (CAST(:area AS text) IS NULL OR s.search_vector @@ plainto_tsquery('portuguese', :area))
                    AND (:perspective = '' OR s.search_vector @@ q.perspective)
                ORDER BY ts_rank_cd(s.search_vector, q.broad_query) DESC,
                    v.id, p.physical_page, s.ordinal
                LIMIT 48
            """),
                    {
                        "search": search_terms(query_terms(facet)),
                        "topic": body.topic_id,
                        "versions": versions,
                        "area": body.filters.area,
                        "perspective": PERSPECTIVES.get(body.perspective, ""),
                    },
                )
                .mappings()
                .all()
            )
            verified = [c for row in rows if (c := verified_citation(row))]
            candidates = [
                {"passage_id": str(c.passage_id), "assertion": assertion}
                for c in verified
                for assertion in support_assertions(c.excerpt, facet, c.title)
            ]
            supported_ids = set(
                connection.execute(
                    text("""
                SELECT DISTINCT passage_id::uuid FROM jsonb_to_recordset(CAST(:candidates AS jsonb))
                    AS candidate(passage_id text, assertion text)
                WHERE to_tsvector('portuguese', assertion) @@ plainto_tsquery('portuguese', :question)
            """),
                    {"candidates": json.dumps(candidates), "question": query_terms(facet)},
                ).scalars()
            )
            verified.sort(key=lambda c: c.passage_id not in supported_ids)
            selected = verified[:8]
            related_ids = {c.passage_id for c in selected}
            supported_ids &= related_ids
            for citation in selected:
                citations[citation.passage_id] = citation
            if related_ids:
                coverage.append(supported_ids or related_ids)
            if supported_ids:
                confirmed += 1
            else:
                gaps.append(f"Não consta confirmação completa para: {facet}.")
    if not facets:
        gaps.append("Não consta evidência: informe os termos ou o ponto que deseja consultar.")
    passages = list(citations.values())
    response = QuestionResponse(
        mode="extractive",
        status="supported" if confirmed == len(facets) and facets else "partial" if passages else "insufficient",
        reference_date=reference,
        claims=[Claim(text=c.excerpt, citations=[c]) for c in passages],
        passages=passages,
        gaps=gaps,
        divergences=[],
    )
    if not passages and not gaps:
        response.gaps.append("Não consta evidência nas versões elegíveis para a data e os filtros informados.")
    if passages and get_settings().bedrock_model_id:
        try:
            generated = generate_claims(body, passages)
            selected = {c.passage_id for claim in generated for c in claim.citations}
            if any(not selected.intersection(evidence) for evidence in coverage):
                raise ValueError("Seleção do modelo perdeu a evidência de um ponto da pergunta.")
            response.claims = generated
            response.mode = "generated"
        except Exception as exc:
            # O modelo nunca controla a elegibilidade, IDs, lacunas ou disponibilidade das fontes.
            logger.warning("Geração indisponível (%s); resposta extrativa preservada.", type(exc).__name__)
            response.notice = "Geração indisponível. Exibindo trechos do acervo com as mesmas fontes."
    return response
