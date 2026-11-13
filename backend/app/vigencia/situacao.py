"""Situação temporal de cada edição: fase declarada, datas e sucessão são lidas separadamente.

A fase impressa (“Vigente”) nunca prova aplicação em qualquer data. A aplicabilidade depende da data de
referência, do intervalo documentado e de uma sucessão declarada pela própria edição sucessora.
"""

import re
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import text

from app.document_parser import CODE

SUCCESSION = re.compile(
    rf"\bsubstitui\s+(?:a\s+)?(?:(?P<code>{CODE})\s+)?"
    r"(?:versão\s*|v\s*)(?P<version>\d+(?:\.\d+)*)\b",
    re.I,
)
# A negação deve governar a declaração, não outra ação da mesma frase.
NEGATED_SUCCESSION = re.compile(r"\b(não|nunca|jamais|tampouco|nem)\b", re.I)
UNCONFIRMED_PROPOSITION = re.compile(
    r"\b(?:não|nunca|jamais|tampouco)\s+(?:se\s+)?(?:(?:deve|pode)\s+)?"
    r"(?:confirm\w*|afirm\w*|comprov\w*|garant\w*|assegur\w*|conclu\w*)\b.*\bque\b",
    re.I | re.S,
)
REJECTED_PROPOSITION = re.compile(r"^\s*[,\"”']*\s*não\s+(?:procede|é\s+verdadeira|se\s+confirma)", re.I)
PREVIOUS_PHASE = re.compile(r"anterior|substituíd", re.I)


def is_affirmative(sentence: str, match: re.Match) -> bool:
    """A declaração vale só se nenhuma negação a governa, antes ou depois do trecho reconhecido."""
    # Vírgulas podem delimitar um inciso, sem encerrar o alcance de “não”.
    prefix = re.sub(r",[^,]*,|\([^)]*\)", " ", sentence[: match.start()])
    prefix = re.split(r"\b(?:mas|porém)\b", prefix, flags=re.I)[-1]
    # A negação de “confirma/afirma que” governa também verbos coordenados.
    if UNCONFIRMED_PROPOSITION.search(prefix):
        return False
    prefix = re.split(r"\be\b", prefix, flags=re.I)[-1]
    if NEGATED_SUCCESSION.search(prefix):
        return False
    return not REJECTED_PROPOSITION.search(sentence[match.end() :])


def affirmative_successions(header):
    for sentence in re.split(r"(?<=[.!?;])\s+", header):
        for declaration in SUCCESSION.finditer(sentence):
            if is_affirmative(sentence, declaration):
                yield declaration


@dataclass
class Successor:
    version: dict
    declaration: str | None = None


@dataclass
class VersionState:
    version: dict
    status: str
    applicable: bool
    successors: list[Successor] = field(default_factory=list)


def ready_versions(connection, topic_id):
    rows = (
        connection.execute(
            text("""
        SELECT v.id, v.document_id, v.version, v.status, v.valid_from, v.valid_until,
               v.superseded_by, v.declared_phase, v.document_type, v.document_layer, v.linked_codes,
               v.created_at, COALESCE(v.title, d.title, v.filename) AS title, d.code,
               COALESCE(p.text, '') AS header
        FROM document_versions v JOIN documents d ON d.id=v.document_id
        LEFT JOIN pages p ON p.version_id=v.id AND p.physical_page=1
        WHERE v.topic_id=:topic AND v.status='ready'
    """),
            {"topic": topic_id},
        )
        .mappings()
        .all()
    )
    return {row["id"]: dict(row) for row in rows}


def declared_successors(version, ready):
    successors = []
    if version["superseded_by"] in ready:
        successors.append(Successor(ready[version["superseded_by"]]))
    # Só sucessão declarada, nunca maior número de versão ou data de upload.
    for successor in ready.values():
        if successor["document_id"] != version["document_id"] or successor["id"] == version["id"]:
            continue
        for declaration in affirmative_successions(successor["header"]):
            code = declaration["code"]
            if code and code.casefold() != (version["code"] or "").casefold():
                continue
            old = declaration["version"]
            matches = [
                v
                for v in ready.values()
                if v["document_id"] == version["document_id"]
                and v["version"]
                and (v["version"] == old or v["version"].startswith(old + "."))
            ]
            if len(matches) == 1 and matches[0]["id"] == version["id"]:
                successors.append(Successor(successor, declaration[0]))
    return successors


def classify(version, successors, reference: date) -> tuple[str, bool]:
    if version["valid_from"] and version["valid_from"] > reference:
        return "a_iniciar", False
    if version["valid_until"] and version["valid_until"] < reference:
        return "encerrada", False
    if any(s.version["valid_from"] is not None and s.version["valid_from"] <= reference for s in successors):
        return "substituida", False
    # Sem início confirmado não se inventa a data de entrada da sucessora.
    if version["declared_phase"] and PREVIOUS_PHASE.search(version["declared_phase"]):
        if not version["valid_from"] or not successors or any(s.version["valid_from"] is None for s in successors):
            return "sem_confirmacao", False
    return ("em_vigor" if version["valid_from"] else "fase_declarada"), True


def version_states(connection, topic_id, reference: date, ready=None) -> dict:
    ready = ready_versions(connection, topic_id) if ready is None else ready
    states = {}
    for version in ready.values():
        successors = declared_successors(version, ready)
        status, applicable = classify(version, successors, reference)
        states[version["id"]] = VersionState(version, status, applicable, successors)
    return states
