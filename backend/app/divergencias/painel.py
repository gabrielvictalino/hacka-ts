"""Apresenta as divergências curadas de um tema conforme as edições publicadas e a data de referência."""

import re
from datetime import date

from sqlalchemy import text

from app.contracts import (
    Citation,
    DeclaredPrecedence,
    DivergenceNotice,
    DivergentGuidance,
    SourceDivergence,
    TopicDivergences,
)
from app.divergencias.catalogo import CURATION_NOTE, CURATOR, DIVERGENCES, REVIEWED_ON, CuratedDivergence
from app.fatos.catalogo import Source
from app.fatos.curadoria import resolve_source
from app.questions import CITATION_COLUMNS, CITATION_JOINS, verified_citation
from app.vigencia.situacao import version_states

NOT_APPLICABLE = {"a_iniciar", "encerrada", "substituida"}
STATUS_TEXT = {
    "a_iniciar": "com vigência a iniciar",
    "encerrada": "com vigência encerrada",
    "substituida": "substituída",
    "sem_confirmacao": "sem aplicação confirmada",
}


def _br(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _label(source: Source) -> str:
    return f"{source.code} v{source.version}, p. {source.page}, item {source.item}"


def _cite(connection, topic_id, source: Source) -> tuple[Citation | None, str | None]:
    """Cita o trecho literal revisado na edição, página e item exatos; nunca outra edição do documento."""
    resolved, reason = resolve_source(connection, topic_id, source)
    if resolved is None:
        return None, reason
    passage_id, literal = resolved
    row = (
        connection.execute(
            text(f"SELECT {CITATION_COLUMNS}, p.text AS page_text {CITATION_JOINS} WHERE s.id=:id"),
            {"id": passage_id},
        )
        .mappings()
        .first()
    )
    citation = verified_citation(row) if row else None
    if citation is None:
        return None, f"{_label(source)}: trecho não confere com a página publicada."
    return citation.model_copy(update={"excerpt": literal, "section": source.item}), None


def _present(connection, topic_id, divergence: CuratedDivergence, states, reference) -> SourceDivergence | None:
    guidances, missing = [], []
    for item in divergence.guidances:
        citation, reason = _cite(connection, topic_id, item.source)
        if citation is None:
            missing.append(reason)
            continue
        state = states[citation.version_id]
        guidances.append(
            DivergentGuidance(
                role=item.role,
                guidance=item.guidance,
                status=state.status,
                applicable=state.applicable,
                citation=citation,
            )
        )
    if not guidances:
        # Nenhuma das fontes revisadas está publicada neste tema.
        return None

    precedence = None
    if divergence.precedence:
        citation, reason = _cite(connection, topic_id, divergence.precedence.source)
        if citation is None:
            missing.append(f"Precedência declarada não localizada. {reason}")
        else:
            prevailing = connection.execute(
                text("SELECT id FROM documents WHERE topic_id=:topic AND lower(code)=lower(:code)"),
                {"topic": topic_id, "code": divergence.precedence.prevailing_code},
            ).scalar()
            precedence = DeclaredPrecedence(
                prevailing_code=divergence.precedence.prevailing_code,
                prevailing_document_id=prevailing,
                statement=divergence.precedence.statement,
                applicable=states[citation.version_id].applicable,
                citation=citation,
            )

    inapplicable = [g for g in guidances if g.status in NOT_APPLICABLE]
    unconfirmed = [g for g in guidances if not g.applicable and g.status not in NOT_APPLICABLE]
    for guidance in unconfirmed:
        missing.append(
            f"{guidance.citation.code} v{guidance.citation.version}: aplicação em {_br(reference)} não confirmada "
            "pelas datas e sucessões documentadas."
        )
    if inapplicable:
        status = "not_applicable"
        editions = "; ".join(f"{g.citation.code} v{g.citation.version} {STATUS_TEXT[g.status]}" for g in inapplicable)
        explanation = (
            f"Fora do cenário em {_br(reference)}: {editions}. As passagens continuam consultáveis como fontes "
            "históricas."
        )
    elif len(guidances) < len(divergence.guidances) or unconfirmed:
        status = "possible"
        explanation = (
            "Possível divergência: falta suporte para confirmar que as orientações se aplicam ao mesmo cenário. "
            "Confira os dados faltantes."
        )
    else:
        status = "confirmed"
        explanation = (
            f"As {len(guidances)} passagens foram localizadas nas edições revisadas e se aplicam em {_br(reference)}. "
            + (
                "O IPBOT mostra a precedência declarada, sem escolher uma das orientações."
                if precedence
                else "A precedência entre as fontes não foi confirmada."
            )
        )
    return SourceDivergence(
        key=divergence.key,
        scenario_id=divergence.scenario_id,
        subject=divergence.subject,
        question=divergence.question,
        scenario=divergence.scenario,
        conditions=list(divergence.conditions),
        consequence=divergence.consequence,
        status=status,
        status_explanation=explanation,
        missing_information=missing,
        guidances=guidances,
        precedence=precedence,
        curated_by=CURATOR,
        reviewed_on=REVIEWED_ON,
    )


def topic_divergences(connection, topic_id, reference: date) -> TopicDivergences:
    states = version_states(connection, topic_id, reference)
    divergences = [
        presented
        for divergence in DIVERGENCES
        if (presented := _present(connection, topic_id, divergence, states, reference))
    ]
    return TopicDivergences(
        topic_id=topic_id, reference_date=reference, curation_note=CURATION_NOTE, divergences=divergences
    )


def _notice(divergence: SourceDivergence) -> DivergenceNotice:
    catalog = next(d for d in DIVERGENCES if d.key == divergence.key)
    codes = list(dict.fromkeys(s.source.code for s in catalog.guidances))
    prefix = "Divergência entre fontes" if divergence.status == "confirmed" else "Possível divergência, não confirmada"
    return DivergenceNotice(
        key=divergence.key,
        subject=divergence.subject,
        status=divergence.status,
        codes=codes,
        message=f"{prefix}: {catalog.notice} Os detalhes ficam com a Gestão do acervo.",
    )


def _mentions(question: str, terms) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", question, re.I) for term in terms)


def divergence_notices(
    connection, topic_id, reference: date, citations: list[Citation] | None = None, question: str = ""
) -> list[DivergenceNotice]:
    """Avisos curtos para a Consulta.

    Com `citations`, só entram as divergências cujas passagens foram recuperadas, ou cujas edições foram
    citadas em uma pergunta sobre o assunto curado.
    """
    terms = {d.key: d.terms for d in DIVERGENCES}
    passages = {c.passage_id for c in citations or ()}
    versions = {c.version_id for c in citations or ()}
    notices = []
    for divergence in topic_divergences(connection, topic_id, reference).divergences:
        if divergence.status == "not_applicable":
            continue
        if citations is not None:
            cited = [g.citation for g in divergence.guidances]
            direct = passages.intersection(c.passage_id for c in cited)
            related = versions.intersection(c.version_id for c in cited) and _mentions(question, terms[divergence.key])
            if not (direct or related):
                continue
        notices.append(_notice(divergence))
    return notices
