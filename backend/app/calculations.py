"""Executa apenas regras conhecidas com fatos curados e fontes elegíveis da consulta."""

import logging

from fastapi import HTTPException
from sqlalchemy import text

from app.bedrock import calculation_claims, generate_claims
from app.config import get_settings
from app.contracts import QuestionRequest, QuestionResponse
from app.db import get_engine
from app.fatos.repositorio import list_facts
from app.regras import ferias, inovacao
from app.regras.base import MissingFacts

logger = logging.getLogger(__name__)
RULES = {
    "ferias.prazos": (ferias.SCHEDULE_KEYS, lambda facts, request: ferias.vacation_schedule(facts, request)),
    "ferias.ausencia_simultanea": (
        ferias.ABSENCE_KEYS,
        lambda facts, request: ferias.simultaneous_absence(facts, request.team_size),
    ),
    "ferias.dias_por_faltas": (
        ferias.UNJUSTIFIED_KEYS,
        lambda facts, request: ferias.vacation_days_by_absences(facts, request.absences),
    ),
    "ferias.ressarcimento": (
        ferias.REIMBURSEMENT_KEYS,
        lambda facts, request: ferias.reimbursement(facts, request.amount),
    ),
    "inovacao.alcada": (
        inovacao.APPROVAL_KEYS,
        lambda facts, request: inovacao.approval_authority(facts, request.amount),
    ),
    "inovacao.orcamento": (inovacao.BUDGET_KEYS, lambda facts, request: inovacao.budget_breakdown(facts)),
    "inovacao.pagamento_premiacao": (
        inovacao.PAYMENT_KEYS,
        lambda facts, request: inovacao.prize_payment_deadline(facts),
    ),
}


def answer_calculation(body: QuestionRequest, eligible_versions, verify) -> QuestionResponse:
    keys, calculate = RULES[body.calculation.rule]
    facts, passages = {}, {}
    with get_engine().connect() as connection:
        if not connection.execute(text("SELECT 1 FROM topics WHERE id=:id"), {"id": body.topic_id}).scalar():
            raise HTTPException(404, "Tema não encontrado.")
        versions = set(eligible_versions(connection, body.topic_id, body.reference_date))
        # A regra explícita determina todos os fatos necessários, inclusive de categorias diferentes.
        candidates = list_facts(connection, keys=keys, topic_id=body.topic_id, area=body.filters.area)
        for fact in candidates:
            verified = []
            for citation in fact.citations:
                if citation.version_id not in versions:
                    break
                row = (
                    connection.execute(
                        text("""
                    SELECT v.id AS version_id, v.document_id, s.id AS passage_id,
                        COALESCE(v.title, d.title, v.filename) AS title, d.code, v.version,
                        p.physical_page, s.excerpt, s.section, v.document_type, v.document_layer,
                        v.declared_phase, v.valid_from, v.valid_until, p.text AS page_text
                    FROM passages s JOIN pages p ON p.id=s.page_id
                    JOIN document_versions v ON v.id=p.version_id JOIN documents d ON d.id=v.document_id
                    WHERE s.id=:passage AND v.id=:version AND v.topic_id=:topic AND v.status='ready'
                """),
                        {"passage": citation.passage_id, "version": citation.version_id, "topic": body.topic_id},
                    )
                    .mappings()
                    .first()
                )
                if row is None or (source := verify(row)) is None:
                    break
                # A curadoria pode citar um recorte; conferir também o recorte, sem confiar no JSON cliente.
                quote = verify({**row, "excerpt": citation.excerpt, "section": citation.section})
                if quote is None:
                    break
                verified.append(quote)
                passages[source.passage_id] = source
            else:
                facts[fact.key] = fact.model_copy(update={"citations": verified})
    response = QuestionResponse(
        mode="extractive",
        status="insufficient",
        reference_date=body.reference_date,
        claims=[],
        passages=[],
        gaps=[],
        divergences=[],
    )
    try:
        result = calculate(facts, body.calculation)
    except MissingFacts:
        response.gaps = [
            "Não consta evidência curada elegível para todos os parâmetros desse cálculo na data e nos filtros informados."
        ]
        return response
    # As fontes retornadas são apenas as efetivamente usadas na memória de cálculo.
    used = {c.passage_id for step in result.steps for c in step.citations}
    response.passages = [source for identifier, source in passages.items() if identifier in used]
    response.calculation = result
    response.claims = calculation_claims(result)
    response.status = "supported"
    if get_settings().bedrock_model_id:
        try:
            response.claims = generate_claims(body, response.passages, result)
            response.mode = "generated"
        except Exception as exc:
            logger.warning("Explicação indisponível (%s); cálculo local preservado.", type(exc).__name__)
            response.notice = "Geração indisponível. Exibindo o cálculo com as mesmas fontes."
    return response
