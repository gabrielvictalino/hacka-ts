from dataclasses import replace
from decimal import Decimal

import pytest
from app.config import DemoAccount, get_settings
from app.db import get_engine
from app.fatos.catalogo import CATALOG, CuratedFact, Source
from app.fatos.curadoria import find_quote, publish_catalog
from app.ingestion import enqueue
from app.main import app
from app.worker import process_one
from conftest import make_pdf
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text

HEADER = """Documento: Norma Geral
Título: Norma de teste
Sigla e Número: NG_9{suffix} Versão: {version}
Fase: Vigente Vigência: 03/08/2026 a 03/02/2028
DOCUMENTO SINTÉTICO.
1. Objetivo
Testar a curadoria."""


@pytest.fixture
def client(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_demo_enabled", True)
    monkeypatch.setattr(settings, "auth_demo_sso_secret", SecretStr("s" * 32))
    monkeypatch.setattr(settings, "auth_cookie_secure", False)
    monkeypatch.setattr(
        settings,
        "auth_demo_users",
        {
            "reader": DemoAccount(name="Leitura", groups=["clause-empregados"]),
            "curator": DemoAccount(name="Gestão", groups=["clause-gestao-acervo"]),
        },
    )
    with TestClient(app) as client:
        yield client


@pytest.fixture
def subject(topic):
    """Tema de teste com nome, código documental exclusivo e limpeza dos fatos antes do tema."""
    with get_engine().connect() as connection:
        name = connection.execute(text("SELECT name FROM topics WHERE id=:id"), {"id": topic}).scalar_one()
    suffix = str(topic.int)[:6]
    yield topic, name, suffix
    with get_engine().begin() as connection:
        connection.execute(text("DELETE FROM curated_facts WHERE topic_id=:id"), {"id": topic})


def ingest(topic, suffix, version, pages):
    content = make_pdf([HEADER.format(suffix=suffix, version=version) + "\n" + pages[0], *pages[1:]])
    with get_engine().begin() as connection:
        result = enqueue(connection, topic, f"NG_9{suffix}-{version}.pdf", content)
    while process_one():
        pass
    return result.version_id


def catalog(name, suffix, version="1.0.0"):
    code = f"NG_9{suffix}"
    return (
        CuratedFact(
            key=f"teste.{suffix}.prazo",
            topic=name,
            category="deadline",
            attribute="prazo_de_solicitacao",
            area="Empregado",
            responsible="Empregado",
            statement="Solicitar com antecedência.",
            value=Decimal(45),
            unit="dias corridos antes do início",
            value_text="Até D-45",
            conditions="Com menos de 45 dias, só por decisão do diretor.",
            sources=(
                Source(code, version, 2, "4.3.1", "antecedência mínima de 45 dias corridos do início de gozo."),
                Source(code, version, 2, "4.3.3", "só por decisão do diretor"),
            ),
            tags=("jornada",),
        ),
        CuratedFact(
            key=f"teste.{suffix}.orcamento",
            topic=name,
            category="value",
            attribute="orcamento_total",
            area="DIRAF",
            responsible="DIRAF",
            statement="Orçamento total.",
            value=Decimal("96000.00"),
            unit="R$",
            value_text="R$ 96.000,00",
            sources=(Source(code, version, 3, "Tabela 1", "Total 96.000,00"),),
        ),
    )


PAGES = [
    "",
    "4.3. Solicitação.\n4.3.1. A solicitação é feita com antecedência\nmínima de 45 dias corridos do início de gozo."
    "\n4.3.3. Com menos de 45 dias, só por decisão do diretor da área.",
    "Tabela 1 — Orçamento\nPremiação 24.000,00\nTotal 96.000,00",
]


def published(topic):
    with get_engine().connect() as connection:
        return connection.execute(
            text("SELECT count(*) FROM curated_facts WHERE topic_id=:id"), {"id": topic}
        ).scalar_one()


def test_find_quote_returns_literal_text_ignoring_only_line_breaks():
    excerpt = "4.5.4. Assinatura do aviso: até 5 dias úteis depois do\nrecebimento."
    assert find_quote(excerpt, "5 dias úteis depois do recebimento.") == "5 dias úteis depois do\nrecebimento."
    assert find_quote(excerpt, "6 dias úteis") is None
    assert find_quote(excerpt, "   ") is None


def test_catalog_covers_ferias_and_inovacao_deadlines_and_values_with_sources():
    keys = [fact.key for fact in CATALOG]
    assert len(keys) == len(set(keys))
    assert {(fact.topic, fact.category) for fact in CATALOG} == {
        ("Férias", "deadline"),
        ("Férias", "value"),
        ("Inovação", "deadline"),
        ("Inovação", "value"),
    }
    for fact in CATALOG:
        assert fact.sources and fact.area and fact.value_text
        assert all(source.page >= 1 and source.item and source.quote.strip() for source in fact.sources)
    by_key = {fact.key: fact for fact in CATALOG}
    total, prizes = by_key["inovacao.orcamento.total"], by_key["inovacao.orcamento.premiacoes"]
    assert (total.value, prizes.value) == (Decimal("96000.00"), Decimal("24000.00"))
    assert total.attribute != prizes.attribute
    assert "24.000,00" in total.conditions and "96.000,00" in prizes.conditions


def test_ingestion_does_not_create_facts_and_curation_publishes_literal_citations(client, subject):
    topic, name, suffix = subject
    version_id = ingest(topic, suffix, "1.0.0", PAGES)
    assert published(topic) == 0

    with get_engine().begin() as connection:
        report = publish_catalog(connection, catalog(name, suffix))
    assert (report.published, report.pending) == (2, 0)

    assert client.post("/api/auth/demo/session", json={"user_id": "reader"}).status_code == 200
    facts = client.get("/fatos", params={"assunto": str(topic)}).json()
    assert [fact["key"] for fact in facts] == [f"teste.{suffix}.prazo", f"teste.{suffix}.orcamento"]
    deadline = facts[0]
    assert deadline["category"] == "deadline" and deadline["area"] == "Empregado"
    assert deadline["value"] == 45 and deadline["unit"] == "dias corridos antes do início"
    assert deadline["conditions"] == "Com menos de 45 dias, só por decisão do diretor."
    assert deadline["tags"] == ["jornada"]
    citation = deadline["citations"][0]
    assert citation["version_id"] == str(version_id)
    assert (citation["code"], citation["version"], citation["physical_page"]) == (f"NG_9{suffix}", "1.0.0", 2)
    assert citation["section"] == "4.3.1"
    assert citation["excerpt"] == "antecedência\nmínima de 45 dias corridos do início de gozo."
    assert [c["section"] for c in deadline["citations"]] == ["4.3.1", "4.3.3"]
    assert facts[1]["citations"][0]["section"] == "Tabela 1"
    assert facts[1]["value"] == 96000


def test_filters_by_category_topic_and_area(client, subject):
    topic, name, suffix = subject
    ingest(topic, suffix, "1.0.0", PAGES)
    with get_engine().begin() as connection:
        publish_catalog(connection, catalog(name, suffix))
    assert client.post("/api/auth/demo/session", json={"user_id": "reader"}).status_code == 200

    def keys(**params):
        response = client.get("/api/fatos", params={"assunto": str(topic), **params})
        assert response.status_code == 200
        return [fact["key"] for fact in response.json()]

    assert keys(categoria="value") == [f"teste.{suffix}.orcamento"]
    assert keys(categoria="deadline", area="empregado") == [f"teste.{suffix}.prazo"]
    assert keys(area="GGC") == []
    assert keys(categoria="risk") == []
    assert client.get("/fatos", params={"categoria": "outra"}).status_code == 422


def test_unverifiable_sources_stay_pending_and_new_editions_are_not_curated(client, subject):
    topic, name, suffix = subject
    ingest(topic, suffix, "1.0.0", PAGES)
    with get_engine().begin() as connection:
        first = publish_catalog(connection, catalog(name, suffix))
    assert first.published == 2

    # Uma nova edição publicada não herda os fatos revisados da anterior.
    ingest(topic, suffix, "2.0.0", ["", "4.3.1. Antecedência mínima de 60 dias.", "Total 99.000,00"])
    with get_engine().begin() as connection:
        report = publish_catalog(connection, catalog(name, suffix, version="2.0.0"))
    assert (report.published, report.pending) == (0, 2)
    assert all(item.reason and "trecho revisado não encontrado" in item.reason for item in report.items)
    assert published(topic) == 0

    with get_engine().begin() as connection:
        missing = publish_catalog(connection, catalog(name, suffix, version="9.9.9"))
    assert "não publicada" in missing.items[0].reason


def test_curation_is_idempotent_and_drops_keys_removed_from_catalog(client, subject):
    topic, name, suffix = subject
    ingest(topic, suffix, "1.0.0", PAGES)
    entries = catalog(name, suffix)
    with get_engine().begin() as connection:
        publish_catalog(connection, entries)
        ids = (
            connection.execute(text("SELECT id FROM curated_facts WHERE topic_id=:id ORDER BY position"), {"id": topic})
            .scalars()
            .all()
        )
        publish_catalog(connection, entries)
        assert (
            connection.execute(text("SELECT id FROM curated_facts WHERE topic_id=:id ORDER BY position"), {"id": topic})
            .scalars()
            .all()
            == ids
        )
        assert (
            connection.execute(
                text("SELECT count(*) FROM fact_citations WHERE fact_id=:id"), {"id": ids[0]}
            ).scalar_one()
            == 2
        )
        publish_catalog(connection, (replace(entries[1], key=entries[1].key),))
    assert published(topic) == 1


def test_fact_routes_require_session_and_curation_requires_management(client, subject):
    assert client.get("/fatos").status_code == 401
    assert client.post("/api/auth/demo/session", json={"user_id": "reader"}).status_code == 200
    assert client.get("/fatos").status_code == 200
    assert client.post("/api/fatos/curadoria").status_code == 403
    assert client.post("/api/auth/demo/session", json={"user_id": "curator"}).status_code == 200
    response = client.post("/api/fatos/curadoria")
    assert response.status_code == 200
    assert response.json()["published"] + response.json()["pending"] == len(CATALOG)


def test_fact_keeps_distinct_excerpts_of_the_same_passage(client, subject):
    topic, name, suffix = subject
    ingest(topic, suffix, "1.0.0", PAGES)
    code = f"NG_9{suffix}"
    entry = replace(
        catalog(name, suffix)[1],
        sources=(
            Source(code, "1.0.0", 3, "Tabela 1", "Premiação 24.000,00"),
            Source(code, "1.0.0", 3, "Tabela 1", "Total 96.000,00"),
            Source(code, "1.0.0", 3, "Tabela 1", "Total 96.000,00"),
        ),
    )
    with get_engine().begin() as connection:
        assert publish_catalog(connection, (entry,)).published == 1
    assert client.post("/api/auth/demo/session", json={"user_id": "reader"}).status_code == 200
    (fact,) = client.get("/fatos", params={"assunto": str(topic)}).json()
    assert [citation["excerpt"] for citation in fact["citations"]] == ["Premiação 24.000,00", "Total 96.000,00"]
    assert len({citation["passage_id"] for citation in fact["citations"]}) == 1
