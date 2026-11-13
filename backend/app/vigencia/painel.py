"""Vigência, camadas, vínculos, precedência declarada e mudanças entre versões de um tema."""

import re
from datetime import date

from sqlalchemy import text

from app.contracts import (
    Citation,
    DocumentLink,
    DocumentValidity,
    PrecedenceDeclaration,
    Succession,
    TopicValidity,
    VersionChange,
    VersionValidity,
)
from app.document_parser import CODE
from app.fatos.curadoria import resolve_source
from app.questions import CITATION_COLUMNS, CITATION_JOINS, verified_citation
from app.vigencia.catalogo import CHANGES, CuratedChange
from app.vigencia.situacao import PREVIOUS_PHASE, is_affirmative, ready_versions, version_states

LAYER_ORDER = (
    "norma geral",
    "procedimento vinculado",
    "apoio",
    "regulamento de programa",
    "instrumento contratual",
    "fundamentação de decisão",
)
PRECEDENCE = re.compile(rf"\bprevalece(?:m|rá)?\s+(?:a|o)\s+(?P<code>{CODE})", re.I)


def _br(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else "data não informada"


def _semver(value: str | None):
    return tuple(int(part) for part in value.split(".")) if value else ()


def _normalized(value: str) -> str:
    return " ".join(value.split()).casefold()


def _citations(connection, where: str, params: dict) -> list[tuple[dict, Citation]]:
    rows = (
        connection.execute(
            text(f"SELECT {CITATION_COLUMNS}, p.text AS page_text {CITATION_JOINS} WHERE {where}"), params
        )
        .mappings()
        .all()
    )
    return [(row, citation) for row in rows if (citation := verified_citation(row))]


def _explanation(state, reference: date) -> str:
    version, phase = state.version, state.version["declared_phase"]
    printed = f"Fase declarada “{phase}”" if phase else "Fase não declarada"
    applied = [s.version for s in state.successors if s.version["valid_from"] and s.version["valid_from"] <= reference]
    match state.status:
        case "em_vigor":
            until = f"a {_br(version['valid_until'])}" if version["valid_until"] else "sem data final impressa"
            applies = f"Aplicável em {_br(reference)}: vigência documentada de {_br(version['valid_from'])} {until}."
            if phase and PREVIOUS_PHASE.search(phase):
                # O rótulo descreve a edição hoje; não impede o uso histórico antes da sucessora.
                applies += f" A fase impressa “{phase}” não afasta o uso nesta data, anterior à sucessora."
            return applies
        case "fase_declarada":
            return (
                f"{printed}. O cabeçalho não informa datas de vigência; a edição é usada em {_br(reference)} "
                "porque nenhuma sucessora declarada está em vigor."
            )
        case "a_iniciar":
            return (
                f"{printed}, mas a vigência começa em {_br(version['valid_from'])}. Não é orientação vigente em "
                f"{_br(reference)}; escolha uma data de referência a partir do início para planejamento."
            )
        case "encerrada":
            return f"Vigência encerrada em {_br(version['valid_until'])}. Permanece consultável como fonte histórica."
        case "substituida":
            successor = applied[0]
            return (
                f"Substituída pela versão {successor['version'] or 'sem número'} a partir de "
                f"{_br(successor['valid_from'])}, conforme declaração da sucessora. "
                "Permanece consultável como fonte histórica."
            )
    declared = ", ".join(s.version["version"] or "sem número" for s in state.successors)
    successor = f"Substituição declarada pela versão {declared}, sem data de início documentada" if declared else ""
    return (
        f"{printed}. {successor or 'Sem data de início ou sucessão confirmada'}. Fica fora das respostas em "
        f"{_br(reference)} e permanece consultável como fonte histórica."
    )


def _notice(current, states, reference: date) -> str | None:
    if len(current) > 1:
        return "Mais de uma edição aplicável na data de referência. Confira as fontes de cada versão."
    if current:
        state = current[0]
        notes = []
        for successor in state.successors:
            if successor.version["valid_from"] and successor.version["valid_from"] > reference:
                notes.append(
                    f"Substituição prevista pela versão {successor.version['version']} a partir de "
                    f"{_br(successor.version['valid_from'])}."
                )
        replaced = [
            other.version["version"]
            for other in states
            if any(s.version["id"] == state.version["id"] for s in other.successors) and not other.applicable
        ]
        if replaced:
            notes.append(
                f"Substitui a versão {', '.join(v or 'sem número' for v in replaced)}, preservada para conferência."
            )
        return " ".join(notes) or None
    upcoming = sorted((s for s in states if s.status == "a_iniciar"), key=lambda s: s.version["valid_from"])
    if upcoming:
        first = upcoming[0].version
        return (
            f"Vigência a iniciar em {_br(first['valid_from'])} (versão {first['version'] or 'sem número'}). "
            f"Não é orientação vigente em {_br(reference)}."
        )
    return f"Nenhuma edição aplicável em {_br(reference)}. As versões continuam disponíveis para conferência."


def _declaration_citations(connection, states) -> dict:
    """Localiza na primeira página da sucessora o trecho que declara a substituição."""
    wanted = {(s.version["id"], s.declaration) for state in states.values() for s in state.successors if s.declaration}
    if not wanted:
        return {}
    found = {}
    for row, citation in _citations(
        connection,
        "v.id = ANY(CAST(:ids AS uuid[])) AND p.physical_page=1 ORDER BY s.ordinal",
        {"ids": sorted({vid for vid, _ in wanted})},
    ):
        for version_id, declaration in wanted:
            if row["version_id"] == version_id and _normalized(declaration) in _normalized(row["excerpt"]):
                found.setdefault((version_id, declaration), citation)
    return found


def _precedence(connection, topic_id, states, documents_by_code) -> dict:
    declarations = {}
    for row, citation in _citations(
        connection,
        "v.topic_id=:topic AND v.status='ready' AND s.excerpt ~* 'prevalece' ORDER BY v.id, p.physical_page, s.ordinal",
        {"topic": topic_id},
    ):
        for sentence in re.split(r"(?<=[.!?;])\s+", " ".join(row["excerpt"].split())):
            for match in PRECEDENCE.finditer(sentence):
                # Mesmas proteções da sucessão: negação antes, inciso ou rejeição depois do código.
                if not is_affirmative(sentence, match):
                    continue
                code = match["code"]
                if code.casefold() == (row["code"] or "").casefold():
                    continue
                key = (row["version_id"], code)
                if key in declarations:
                    continue
                state = states.get(row["version_id"])
                declarations[key] = (
                    row["document_id"],
                    PrecedenceDeclaration(
                        prevailing_code=code,
                        prevailing_document_id=documents_by_code.get(code.casefold()),
                        applicable=bool(state and state.applicable),
                        citation=citation,
                    ),
                )
    grouped = {}
    for document_id, declaration in declarations.values():
        grouped.setdefault(document_id, []).append(declaration)
    return grouped


def _changes(connection, topic_id, ready, states) -> list[VersionChange]:
    by_edition = {((v["code"] or "").casefold(), v["version"]): v["id"] for v in ready.values()}
    changes = []
    for change in CHANGES:
        to_id = by_edition.get((change.code.casefold(), change.to_version))
        if to_id is None:
            continue
        resolved = _resolve_change(connection, topic_id, change)
        if resolved is None:
            continue
        before, after = resolved
        from_id = by_edition.get((change.code.casefold(), change.from_version))
        changes.append(
            VersionChange(
                key=change.key,
                code=change.code,
                attribute=change.attribute,
                summary=change.summary,
                from_version=change.from_version,
                to_version=change.to_version,
                from_version_id=from_id,
                to_version_id=to_id,
                before_text=change.before_text,
                after_text=change.after_text,
                previous_available=from_id is not None,
                # A mudança só vale na data em que a edição nova é aplicável.
                in_effect=states[to_id].applicable,
                to_status=states[to_id].status,
                to_valid_from=ready[to_id]["valid_from"],
                to_valid_until=ready[to_id]["valid_until"],
                note=change.note,
                before_citations=before,
                after_citations=after,
            )
        )
    return changes


def _resolve_change(connection, topic_id, change: CuratedChange):
    groups = []
    for sources in (change.before, change.after):
        citations = []
        for source in sources:
            resolved, _ = resolve_source(connection, topic_id, source)
            if resolved is None:
                # Uma mudança sem todas as fontes revisadas não é apresentada.
                return None
            passage_id, literal = resolved
            found = _citations(connection, "s.id=:id", {"id": passage_id})
            if not found:
                return None
            citations.append(found[0][1].model_copy(update={"excerpt": literal, "section": source.item}))
        groups.append(citations)
    return groups


def topic_validity(connection, topic_id, reference: date) -> TopicValidity:
    ready = ready_versions(connection, topic_id)
    states = version_states(connection, topic_id, reference, ready)
    declarations = _declaration_citations(connection, states)
    headers = (
        {
            row["version_id"]: citation
            for row, citation in _citations(
                connection,
                "v.id = ANY(CAST(:ids AS uuid[])) AND p.physical_page=1 AND s.ordinal=0",
                {"ids": list(ready)},
            )
            if re.search(r"\b(?:Fase|Vigência)\s*:", row["excerpt"])
        }
        if ready
        else {}
    )
    documents_by_code = {(v["code"] or "").casefold(): v["document_id"] for v in ready.values() if v["code"]}
    precedence = _precedence(connection, topic_id, states, documents_by_code)

    def succession(other, successor):
        """`other` é a edição exibida na relação; a vigência da sucessão é sempre a da sucessora."""
        start = successor.version["valid_from"]
        return Succession(
            version_id=other["id"],
            version=other["version"],
            valid_from=other["valid_from"],
            in_effect=bool(start and start <= reference),
            citation=declarations.get((successor.version["id"], successor.declaration)),
        )

    supersedes = {}
    for state in states.values():
        for successor in state.successors:
            supersedes.setdefault(successor.version["id"], []).append(succession(state.version, successor))

    by_document = {}
    for state in states.values():
        by_document.setdefault(state.version["document_id"], []).append(state)
    documents = []
    for document_id, document_states in by_document.items():
        document_states.sort(
            key=lambda s: (s.version["valid_from"] or date.min, _semver(s.version["version"]), s.version["created_at"]),
            reverse=True,
        )
        current = [s for s in document_states if s.applicable]
        representative = (current or document_states)[0].version
        documents.append(
            DocumentValidity(
                document_id=document_id,
                code=representative["code"],
                title=representative["title"],
                document_type=representative["document_type"],
                document_layer=representative["document_layer"],
                current_version_ids=[s.version["id"] for s in current],
                notice=_notice(current, document_states, reference),
                links=[
                    DocumentLink(code=code, document_id=documents_by_code.get(code.casefold()))
                    for code in representative["linked_codes"]
                ],
                precedence=precedence.get(document_id, []),
                versions=[
                    VersionValidity(
                        version_id=s.version["id"],
                        version=s.version["version"],
                        title=s.version["title"],
                        declared_phase=s.version["declared_phase"],
                        valid_from=s.version["valid_from"],
                        valid_until=s.version["valid_until"],
                        linked_codes=s.version["linked_codes"],
                        status=s.status,
                        applicable=s.applicable,
                        explanation=_explanation(s, reference),
                        superseded_by=[succession(x.version, x) for x in s.successors],
                        supersedes=supersedes.get(s.version["id"], []),
                        header_citation=headers.get(s.version["id"]),
                    )
                    for s in document_states
                ],
            )
        )
    layer = {name: index for index, name in enumerate(LAYER_ORDER)}
    documents.sort(key=lambda d: (layer.get(d.document_layer, len(layer)), d.code or "", d.title))
    return TopicValidity(
        topic_id=topic_id,
        reference_date=reference,
        documents=documents,
        changes=_changes(connection, topic_id, ready, states),
    )
