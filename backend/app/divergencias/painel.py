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
from app.fatos.curadoria import find_quote
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


def _edition(states, source: Source):
    """Edição revisada entre as já classificadas na data, por código e versão, independentemente do trecho.

    Usar o mesmo conjunto da vigência evita citar uma edição publicada depois da classificação.
    """
    found = sorted(
        (s.version["created_at"], vid)
        for vid, s in states.items()
        if (s.version["code"] or "").casefold() == source.code.casefold() and s.version["version"] == source.version
    )
    return found[0][1] if found else None


def _cite(connection, edition, source: Source) -> tuple[Citation | None, str | None]:
    """Cita o trecho literal revisado na edição, página e item exatos; outro item da página não serve."""
    rows = (
        connection.execute(
            text(f"""SELECT {CITATION_COLUMNS}, p.text AS page_text {CITATION_JOINS}
                WHERE v.id=:version AND p.physical_page=:page AND s.section=:item ORDER BY s.ordinal"""),
            {"version": edition, "page": source.page, "item": source.item},
        )
        .mappings()
        .all()
    )
    if not rows:
        return None, f"{_label(source)}: item não localizado na página publicada."
    for row in rows:
        literal = find_quote(row["excerpt"], source.quote)
        if literal and (citation := verified_citation(row)):
            return citation.model_copy(update={"excerpt": literal, "section": source.item}), None
    return None, f"{_label(source)}: trecho revisado não encontrado no item publicado."


def _present(connection, topic_id, divergence: CuratedDivergence, states, reference):
    """Devolve a divergência e as edições envolvidas; nenhuma edição publicada no tema, nenhuma divergência."""
    guidances, missing, editions = [], [], {}
    for item in divergence.guidances:
        source = item.source
        edition = _edition(states, source)
        if edition is None:
            missing.append(f"{source.code} v{source.version}: edição não publicada no tema.")
            continue
        # A vigência vale para a edição mesmo quando o trecho revisado não é localizado.
        state = states[edition]
        editions[edition] = (source, state)
        citation, reason = _cite(connection, edition, source)
        if citation is None:
            missing.append(reason)
            continue
        guidances.append(
            DivergentGuidance(
                role=item.role,
                guidance=item.guidance,
                status=state.status,
                applicable=state.applicable,
                citation=citation,
            )
        )
    if not editions:
        return None

    precedence = None
    if divergence.precedence:
        edition = _edition(states, divergence.precedence.source)
        citation, reason = (
            _cite(connection, edition, divergence.precedence.source)
            if edition
            else (None, f"{_label(divergence.precedence.source)}: edição não publicada no tema.")
        )
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

    inapplicable = [(s, st) for s, st in editions.values() if st.status in NOT_APPLICABLE]
    # Sem data de início, a fase declarada não confirma a aplicação na data consultada.
    unconfirmed = [
        (s, st)
        for s, st in editions.values()
        if st.status not in NOT_APPLICABLE and (not st.applicable or st.status == "fase_declarada")
    ]
    for source, state in unconfirmed:
        reason = (
            "data de início da vigência não informada no cabeçalho"
            if state.status == "fase_declarada"
            else "não confirmada pelas datas e sucessões documentadas"
        )
        missing.append(f"{source.code} v{source.version}: aplicação em {_br(reference)} {reason}.")
    if inapplicable:
        status = "not_applicable"
        listed = "; ".join(f"{s.code} v{s.version} {STATUS_TEXT[st.status]}" for s, st in inapplicable)
        explanation = (
            f"Fora do cenário em {_br(reference)}: {listed}. As passagens continuam consultáveis como fontes "
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
    presented = SourceDivergence(
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
    return presented, set(editions)


def _presented(connection, topic_id, reference: date):
    states = version_states(connection, topic_id, reference)
    return [
        result
        for divergence in DIVERGENCES
        if (result := _present(connection, topic_id, divergence, states, reference))
    ]


def topic_divergences(connection, topic_id, reference: date) -> TopicDivergences:
    divergences = [presented for presented, _ in _presented(connection, topic_id, reference)]
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
    for divergence, editions in _presented(connection, topic_id, reference):
        if divergence.status == "not_applicable":
            continue
        if citations is not None:
            direct = passages.intersection(g.citation.passage_id for g in divergence.guidances)
            related = versions.intersection(editions) and _mentions(question, terms[divergence.key])
            if not (direct or related):
                continue
        notices.append(_notice(divergence))
    return notices
