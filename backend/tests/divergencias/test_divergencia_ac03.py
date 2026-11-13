import pytest
from app.auth import current_identity
from app.contracts import Identity, Permission, Role
from app.db import get_engine
from app.divergencias import painel
from app.divergencias.catalogo import DIVERGENCES
from app.ingestion import enqueue
from app.main import app
from app.worker import process_one
from conftest import make_pdf
from fastapi.testclient import TestClient

NG_HEADER = """Documento: Norma Geral
Título: Férias
Sigla e Número: NG_111 Versão: 3.0.0
Fase: Vigente Vigência: 03/08/2026 a 03/02/2028
DOCUMENTO SINTÉTICO.
2.2. Esta norma substitui a NG_111 versão 2.0.0."""
PX_HEADER = """Documento: Procedimento
Título: Procedimento de Férias
Sigla e Número: PX_1111-001 Versão: 1.0.0
Fase: Vigente Vigência: 10/08/2026 a 10/02/2028
Vinculado a: NG_111
DOCUMENTO SINTÉTICO."""
PRECEDENCE = """2.2. O procedimento herda a numeração da NG_111 e a ela se subordina. Em
divergência, prevalece a NG_111."""
NG_NOTICE = """4.5.2. Decisão do gestor imediato: até 7 dias corridos depois do registro da solicitação.
4.5.3. Emissão do aviso pela GGC: até 35 dias antes.
4.5.4. Assinatura do aviso pelo empregado: até 5 dias úteis depois do recebimento."""
PX_NOTICE = """8.4. Emitir o aviso (até D-35).
8.4.1. Cabe à GGC conferir o saldo e as faltas conforme o TB_1111-001 e emitir o aviso a partir da fila.
8.4.2. Se a solicitação foi aprovada com menos de 35 dias para o início, a GGC
emite o aviso no dia seguinte à aprovação."""
KEY = "ferias.aviso.aprovacao_com_menos_de_35_dias"


def identity(role: Role) -> Identity:
    permissions = [Permission.read]
    if role == Role.gestao:
        permissions += [Permission.ingest, Permission.curate, Permission.read_alerts]
    return Identity(subject=role.value, name=role.value, role=role, permissions=permissions, simulated=True)


@pytest.fixture
def client():
    app.dependency_overrides[current_identity] = lambda: identity(Role.gestao)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def ingest(topic, name, pages):
    with get_engine().begin() as connection:
        version = enqueue(connection, topic, name, make_pdf(pages)).version_id
    assert process_one()
    return str(version)


def acervo(topic, precedence=PRECEDENCE, px_notice=PX_NOTICE):
    ng = ingest(topic, "NG_111.pdf", [NG_HEADER, "4.3.1. Solicitação com 45 dias.", NG_NOTICE])
    px = ingest(topic, "PX_1111-001.pdf", [f"{PX_HEADER}\n{precedence}", "8.3. Decidir.", px_notice])
    return ng, px


def details(client, topic, reference="2026-11-13"):
    response = client.get("/api/divergencias", params={"topic_id": str(topic), "reference_date": reference})
    assert response.status_code == 200, response.text
    return response.json()


def notices(client, topic, reference="2026-11-13"):
    response = client.get("/api/divergencias/avisos", params={"topic_id": str(topic), "reference_date": reference})
    assert response.status_code == 200, response.text
    return response.json()


def test_catalog_declares_ac03_with_two_passages_and_precedence():
    (ac03,) = DIVERGENCES
    assert ac03.scenario_id == "AC-03"
    assert [(g.source.code, g.source.version, g.source.page, g.source.item) for g in ac03.guidances] == [
        ("NG_111", "3.0.0", 3, "4.5.3"),
        ("PX_1111-001", "1.0.0", 3, "8.4.2"),
    ]
    precedence = ac03.precedence.source
    assert (precedence.code, precedence.version, precedence.page, precedence.item) == ("PX_1111-001", "1.0.0", 1, "2.2")
    assert ac03.precedence.prevailing_code == "NG_111"


def test_management_sees_curated_divergence_with_navigable_citations(client, topic):
    ng, px = acervo(topic)
    result = details(client, topic)
    assert "curadoria manual" in result["curation_note"] and "evolução" in result["curation_note"]
    (divergence,) = result["divergences"]
    assert divergence["key"] == KEY and divergence["scenario_id"] == "AC-03"
    assert divergence["kind"] == "source_divergence" and divergence["curation"] == "manual"
    assert divergence["status"] == "confirmed" and divergence["missing_information"] == []
    assert "D-32" in divergence["scenario"] and divergence["conditions"]
    norm, procedure = divergence["guidances"]
    assert (norm["citation"]["version_id"], norm["citation"]["physical_page"], norm["citation"]["section"]) == (
        ng,
        3,
        "4.5.3",
    )
    assert norm["citation"]["excerpt"] == "Emissão do aviso pela GGC: até 35 dias antes."
    assert (procedure["citation"]["version_id"], procedure["citation"]["physical_page"]) == (px, 3)
    assert procedure["citation"]["section"] == "8.4.2"
    assert "no dia seguinte à aprovação" in procedure["citation"]["excerpt"]
    assert all(g["applicable"] and g["status"] == "em_vigor" for g in divergence["guidances"])
    precedence = divergence["precedence"]
    assert precedence["prevailing_code"] == "NG_111" and precedence["applicable"]
    assert precedence["prevailing_document_id"] == norm["citation"]["document_id"]
    assert (precedence["citation"]["version_id"], precedence["citation"]["physical_page"]) == (px, 1)
    # Cada citação abre a versão e a página publicadas.
    for citation in (norm["citation"], procedure["citation"], precedence["citation"]):
        opened = client.get(f"/api/citations/{citation['passage_id']}").json()
        assert (opened["version_id"], opened["physical_page"]) == (citation["version_id"], citation["physical_page"])
        assert " ".join(citation["excerpt"].split()) in " ".join(opened["excerpt"].split())


def test_consulta_gets_only_short_notice(client, topic):
    acervo(topic)
    app.dependency_overrides[current_identity] = lambda: identity(Role.empregado)
    assert client.get("/api/divergencias", params={"topic_id": str(topic)}).status_code == 403
    (notice,) = notices(client, topic)
    assert notice == {
        "key": KEY,
        "kind": "source_divergence",
        "subject": notice["subject"],
        "status": "confirmed",
        "codes": ["NG_111", "PX_1111-001"],
        "message": notice["message"],
    }
    assert "Gestão do acervo" in notice["message"] and "35 dias" in notice["message"]

    answer = client.post(
        "/perguntar",
        json={
            "topic_id": str(topic),
            "question": "Quando a GGC emite o aviso?",
            "reference_date": "2026-11-13",
        },
    ).json()
    assert [n["key"] for n in answer["divergence_notices"]] == [KEY]
    # Os detalhes ficam na Gestão; a Consulta não recebe cenário nem precedência.
    assert answer["divergences"] == []
    unrelated = client.post(
        "/perguntar",
        json={"topic_id": str(topic), "question": "Decidir", "reference_date": "2026-11-13"},
    ).json()
    assert unrelated["divergence_notices"] == []


def test_question_about_the_subject_citing_an_involved_edition_gets_the_notice(client, topic):
    from datetime import date

    from app.contracts import Citation

    acervo(topic)
    answer = client.post(
        "/perguntar",
        json={"topic_id": str(topic), "question": "Solicitação com 45 dias", "reference_date": "2026-11-13"},
    ).json()
    other = [Citation.model_validate(c) for c in answer["passages"] if c["section"] == "4.3.1"]
    assert other
    with get_engine().connect() as connection:
        found = painel.divergence_notices(connection, topic, date(2026, 11, 13), other, "E o aviso de férias?")
        assert [n.key for n in found] == [KEY]
        assert painel.divergence_notices(connection, topic, date(2026, 11, 13), other, "Solicitação") == []
        assert painel.divergence_notices(connection, topic, date(2026, 11, 13), [], "aviso") == []


def test_divergence_is_separate_from_version_changes(client, topic):
    acervo(topic)
    validity = client.get("/api/vigencia", params={"topic_id": str(topic), "reference_date": "2026-11-13"}).json()
    assert all(change["kind"] == "version_change" for change in validity["changes"])
    assert KEY not in {change["key"] for change in validity["changes"]}


def test_edition_outside_reference_date_is_not_presented_as_current_divergence(client, topic):
    acervo(topic)
    # O PX_1111-001 só começa em 10/08/2026.
    (divergence,) = details(client, topic, "2026-08-05")["divergences"]
    assert divergence["status"] == "not_applicable"
    assert "PX_1111-001 v1.0.0 com vigência a iniciar" in divergence["status_explanation"]
    assert notices(client, topic, "2026-08-05") == []


def test_missing_passage_is_reported_as_unconfirmed(client, topic):
    acervo(topic, px_notice="8.4. Emitir o aviso (até D-35).")
    (divergence,) = details(client, topic)["divergences"]
    assert divergence["status"] == "possible"
    assert [g["citation"]["code"] for g in divergence["guidances"]] == ["NG_111"]
    assert any("8.4.2" in item for item in divergence["missing_information"])
    (notice,) = notices(client, topic)
    assert notice["status"] == "possible" and "não confirmada" in notice["message"]


def test_missing_precedence_is_declared_without_choosing_a_source(client, topic):
    acervo(topic, precedence="2.1. Histórico de versões.")
    (divergence,) = details(client, topic)["divergences"]
    assert divergence["status"] == "confirmed" and divergence["precedence"] is None
    assert any("Precedência declarada não localizada" in item for item in divergence["missing_information"])
    assert "precedência entre as fontes não foi confirmada" in divergence["status_explanation"]


def test_topic_without_reviewed_sources_has_no_divergence(client, topic):
    ingest(topic, "NG_903.pdf", [NG_HEADER.replace("NG_111", "NG_903"), NG_NOTICE])
    assert details(client, topic)["divergences"] == []
    assert notices(client, topic) == []


def test_divergence_routes_require_session_and_existing_topic(client, topic, monkeypatch):
    from uuid import uuid4

    assert client.get("/api/divergencias", params={"topic_id": str(uuid4())}).status_code == 404
    monkeypatch.setattr(painel, "DIVERGENCES", ())
    assert details(client, topic)["divergences"] == []
    app.dependency_overrides.clear()
    assert client.get("/api/divergencias", params={"topic_id": str(topic)}).status_code == 401
    assert client.get("/api/divergencias/avisos", params={"topic_id": str(topic)}).status_code == 401
