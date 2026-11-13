import pytest
from app.auth import current_identity
from app.db import get_engine
from app.fatos.catalogo import Source
from app.ingestion import enqueue
from app.main import app
from app.vigencia import painel
from app.vigencia.catalogo import CuratedChange
from app.worker import process_one
from conftest import make_pdf
from fastapi.testclient import TestClient


@pytest.fixture
def reader():
    app.dependency_overrides[current_identity] = lambda: None
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def ingest(topic, texts, name="fonte.pdf"):
    with get_engine().begin() as connection:
        version = enqueue(connection, topic, name, make_pdf(texts)).version_id
    assert process_one()
    return str(version)


def header(code, version, phase, validity=None, extra=""):
    lines = [f"Título: Norma {code}", f"Sigla e Número: {code}", f"Versão: {version}", f"Fase: {phase}"]
    if validity:
        lines.append(f"Vigência: {validity}")
    return "\n".join(lines) + (f"\n{extra}" if extra else "")


def validity(reader, topic, reference):
    response = reader.get("/api/vigencia", params={"topic_id": str(topic), "reference_date": reference})
    assert response.status_code == 200, response.text
    return response.json()


def document(result, code):
    return next(d for d in result["documents"] if d["code"] == code)


def version(doc, number):
    return next(v for v in doc["versions"] if v["version"] == number)


def ask(reader, topic, question, reference):
    response = reader.post(
        "/perguntar", json={"topic_id": str(topic), "question": question, "reference_date": reference}
    )
    assert response.status_code == 200, response.text
    return {c["version_id"] for c in response.json()["passages"]}


def test_succession_keeps_previous_version_and_citations(reader, topic):
    old = ingest(
        topic,
        [header("NG_901", "2.0.0", "Versão anterior", "10/12/2025 a 10/06/2027"), "1. Férias: prazo de 30 dias."],
    )
    new = ingest(
        topic,
        [
            header(
                "NG_901", "3.0.0", "Vigente", "03/08/2026 a 03/02/2028", "Esta norma substitui a NG_901 versão 2.0.0."
            ),
            "1. Férias: prazo de 45 dias.",
        ],
    )
    current = document(validity(reader, topic, "2026-11-13"), "NG_901")
    assert current["current_version_ids"] == [new]
    assert [v["version"] for v in current["versions"]] == ["3.0.0", "2.0.0"]
    assert "Substitui a versão 2.0.0" in current["notice"]
    v3, v2 = version(current, "3.0.0"), version(current, "2.0.0")
    assert (v3["status"], v3["applicable"], v3["declared_phase"]) == ("em_vigor", True, "Vigente")
    assert (v2["status"], v2["applicable"]) == ("substituida", False)
    # Fase, datas e substituição continuam separadas.
    assert v2["declared_phase"] == "Versão anterior" and v2["valid_until"] == "2027-06-10"
    succession = v2["superseded_by"][0]
    assert succession["version_id"] == new and succession["in_effect"]
    assert "substitui a NG_901 versão 2.0.0" in succession["citation"]["excerpt"]
    assert succession["citation"]["version_id"] == new and succession["citation"]["physical_page"] == 1
    assert v3["supersedes"][0]["version_id"] == old
    assert "Fase: Versão anterior" in v2["header_citation"]["excerpt"]
    assert reader.get(f"/api/citations/{v2['header_citation']['passage_id']}").json() == v2["header_citation"]
    assert ask(reader, topic, "Prazo de férias", "2026-11-13") == {new}

    historic = document(validity(reader, topic, "2026-07-10"), "NG_901")
    assert historic["current_version_ids"] == [old]
    assert version(historic, "2.0.0")["status"] == "em_vigor"
    assert "Versão anterior" in version(historic, "2.0.0")["explanation"]
    assert version(historic, "3.0.0")["status"] == "a_iniciar"
    assert "Substituição prevista pela versão 3.0.0 a partir de 03/08/2026" in historic["notice"]
    assert not version(historic, "2.0.0")["superseded_by"][0]["in_effect"]
    assert ask(reader, topic, "Prazo de férias", "2026-07-10") == {old}


def test_declared_vigente_label_is_not_proof_before_documented_start(reader, topic):
    contract = ingest(
        topic,
        [
            header("CTR_2099-001", "1.0.0", "Vigente", "30/11/2026 a 29/04/2027"),
            "CLÁUSULA PRIMEIRA - Locação: valor de R$ 3.650,00.",
        ],
    )
    before = document(validity(reader, topic, "2026-11-13"), "CTR_2099-001")
    state = before["versions"][0]
    assert state["declared_phase"] == "Vigente"
    assert (state["status"], state["applicable"]) == ("a_iniciar", False)
    assert before["current_version_ids"] == []
    assert "Vigência a iniciar em 30/11/2026" in before["notice"]
    assert "Não é orientação vigente em 13/11/2026" in state["explanation"]
    assert ask(reader, topic, "Valor da locação", "2026-11-13") == set()

    started = document(validity(reader, topic, "2026-12-01"), "CTR_2099-001")
    assert started["current_version_ids"] == [contract] and started["versions"][0]["status"] == "em_vigor"
    assert ask(reader, topic, "Valor da locação", "2026-12-01") == {contract}
    assert document(validity(reader, topic, "2027-05-01"), "CTR_2099-001")["versions"][0]["status"] == "encerrada"


def test_phase_without_dates_is_reported_as_declared_only(reader, topic):
    ingest(topic, [header("FM_902-001", "1.0.0", "Vigente"), "Bloco A - Prazo de 45 dias."])
    state = document(validity(reader, topic, "2026-11-13"), "FM_902-001")["versions"][0]
    assert state["status"] == "fase_declarada" and state["applicable"]
    assert state["valid_from"] is None and "não informa datas" in state["explanation"]


def test_layers_links_and_documented_precedence(reader, topic):
    norm = ingest(topic, [header("NG_903", "1.0.0", "Vigente", "01/01/2026 a 31/12/2027"), "1. Regra geral."])
    ingest(
        topic,
        [
            header("PX_903-001", "1.0.0", "Vigente", "01/02/2026 a 31/12/2027", "Vinculado a: NG_903 e NG_012"),
            "2.2. O procedimento se subordina. Em divergência, prevalece a NG_903.\n"
            "2.3. Este anexo não prevalece a NG_012.",
        ],
    )
    result = validity(reader, topic, "2026-11-13")
    assert [d["code"] for d in result["documents"]] == ["NG_903", "PX_903-001"]
    procedure = document(result, "PX_903-001")
    norm_doc = document(result, "NG_903")
    assert (norm_doc["document_layer"], procedure["document_layer"]) == ("norma geral", "procedimento vinculado")
    assert procedure["links"] == [
        {"code": "NG_903", "document_id": norm_doc["document_id"]},
        {"code": "NG_012", "document_id": None},
    ]
    [precedence] = procedure["precedence"]
    assert precedence["prevailing_code"] == "NG_903" and precedence["applicable"]
    assert precedence["prevailing_document_id"] == norm_doc["document_id"]
    assert precedence["citation"]["section"] == "2.2" and "prevalece a NG_903" in precedence["citation"]["excerpt"]
    assert norm_doc["current_version_ids"] == [norm] and norm_doc["precedence"] == []
    # Antes do início do procedimento, a precedência que ele declara não se aplica.
    assert not document(validity(reader, topic, "2026-01-15"), "PX_903-001")["precedence"][0]["applicable"]


def test_curated_version_change_is_not_a_conflict(reader, topic, monkeypatch):
    ingest(topic, [header("FM_904-001", "1.0.0", "Versão anterior"), "Enviar com antecedência mínima de 30 dias."])
    new = ingest(
        topic,
        [
            header("FM_904-001", "2.0.0", "Vigente", extra="Substitui a versão 1.0.0."),
            "Bloco D - Exige 45 dias de antecedência.",
        ],
    )
    ingest(
        topic, [header("RG_905", "2.0.0", "Vigente"), "2.1. Primeira edição: até 3 ideias. Edição atual: até 2 ideias."]
    )
    change = CuratedChange(
        key="teste.fm904",
        code="FM_904-001",
        attribute="antecedencia",
        summary="Antecedência",
        from_version="1.0.0",
        to_version="2.0.0",
        before_text="30 dias",
        after_text="45 dias",
        before=(Source("FM_904-001", "1.0.0", 2, "Instrução", "antecedência mínima de 30 dias"),),
        after=(Source("FM_904-001", "2.0.0", 2, "Bloco D", "Exige 45 dias de antecedência."),),
    )
    without_previous = CuratedChange(
        key="teste.rg905",
        code="RG_905",
        attribute="ideias",
        summary="Ideias",
        from_version="1.0.0",
        to_version="2.0.0",
        before_text="Até 3",
        after_text="Até 2",
        before=(),
        after=(Source("RG_905", "2.0.0", 2, "2.1", "até 3 ideias"),),
        note="Versão anterior fora do acervo.",
    )
    unresolved = CuratedChange(
        key="teste.ausente",
        code="FM_904-001",
        attribute="x",
        summary="x",
        from_version="1.0.0",
        to_version="2.0.0",
        before_text="x",
        after_text="y",
        before=(),
        after=(Source("FM_904-001", "2.0.0", 2, "Bloco D", "trecho que não existe"),),
    )
    other_topic = CuratedChange(
        key="teste.outro",
        code="NG_999",
        attribute="x",
        summary="x",
        from_version="1.0.0",
        to_version="2.0.0",
        before_text="x",
        after_text="y",
        before=(),
        after=(Source("NG_999", "2.0.0", 1, "1", "x"),),
    )
    monkeypatch.setattr(painel, "CHANGES", (change, without_previous, unresolved, other_topic))
    result = validity(reader, topic, "2026-11-13")
    assert [c["key"] for c in result["changes"]] == ["teste.fm904", "teste.rg905"]
    fm, rg = result["changes"]
    assert fm["kind"] == "version_change" and fm["previous_available"] and fm["to_version_id"] == new
    assert fm["before_citations"][0]["excerpt"] == "antecedência mínima de 30 dias"
    assert fm["before_citations"][0]["version"] == "1.0.0" and fm["before_citations"][0]["section"] == "Instrução"
    assert fm["after_citations"][0]["physical_page"] == 2 and fm["after_citations"][0]["version_id"] == new
    assert not rg["previous_available"] and rg["from_version_id"] is None and rg["before_citations"] == []
    assert rg["note"] == "Versão anterior fora do acervo."
    # Mudança de versão não aparece como divergência na consulta.
    response = reader.post("/perguntar", json={"topic_id": str(topic), "question": "Antecedência do formulário"})
    assert response.json()["divergences"] == []


def test_reference_catalog_matches_the_acervo_layout():
    keys = [change.key for change in painel.CHANGES]
    assert len(keys) == len(set(keys))
    for change in painel.CHANGES:
        assert change.after and all(s.code == change.code for s in (*change.before, *change.after))
        assert all(s.version == change.from_version for s in change.before)
        assert {s.version for s in change.after} == {change.to_version}


def test_validity_requires_session_and_existing_topic(reader, topic):
    from uuid import uuid4

    assert reader.get("/api/vigencia", params={"topic_id": str(uuid4())}).status_code == 404
    assert reader.get("/vigencia", params={"topic_id": str(topic)}).status_code == 200
    app.dependency_overrides.clear()
    assert reader.get("/api/vigencia", params={"topic_id": str(topic)}).status_code == 401
