import json
from decimal import Decimal
from uuid import uuid4

import pytest
from app.auth import current_identity
from app.config import get_settings
from app.db import get_engine
from app.fatos.catalogo import CuratedFact, Source
from app.fatos.curadoria import publish_catalog
from app.ingestion import enqueue
from app.main import app
from app.worker import process_one
from conftest import make_pdf
from fastapi.testclient import TestClient
from sqlalchemy import text


@pytest.fixture
def reader():
    app.dependency_overrides[current_identity] = lambda: None
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def refund_fact(topic):
    code = f"NG_9{str(topic.int)[:6]}"
    quote = "4.1 O ressarcimento é limitado a R$ 2.500,00 por evento, mediante comprovação."
    pdf = make_pdf(
        [
            f"Título: Norma de ressarcimento\nSigla e Número: {code}\nVersão: 1.0.0\n"
            "Fase: Vigente\nVigência: 01/01/2026 a 31/12/2028",
            quote,
        ]
    )
    with get_engine().begin() as connection:
        name = connection.execute(text("SELECT name FROM topics WHERE id=:id"), {"id": topic}).scalar_one()
        version = enqueue(connection, topic, "fonte.pdf", pdf).version_id
    assert process_one()
    fact = CuratedFact(
        key="ferias.ressarcimento.limite",
        topic=name,
        category="value",
        attribute="limite",
        area="GGC",
        responsible="GGC",
        statement="Ressarcimento limitado por evento.",
        value=Decimal("2500"),
        value_text="R$ 2.500,00",
        unit="reais",
        conditions="Por evento, mediante comprovação.",
        sources=(Source(code, "1.0.0", 2, "4.1", quote),),
    )
    with get_engine().begin() as connection:
        assert publish_catalog(connection, (fact,)).published == 1
    yield version
    with get_engine().begin() as connection:
        connection.execute(text("DELETE FROM curated_facts WHERE topic_id=:id"), {"id": topic})


def ask(reader, topic, **updates):
    body = {
        "topic_id": str(topic),
        "question": "Explique o ressarcimento.",
        "reference_date": "2026-11-13",
        "calculation": {"rule": "ferias.ressarcimento", "amount": 3000},
    }
    response = reader.post("/perguntar", json={**body, **updates})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def model(monkeypatch):
    import boto3

    received = []

    def setup(failure=None):
        class Client:
            def close(self):
                pass

            def converse(self, **kwargs):
                payload = json.loads(kwargs["messages"][0]["content"][0]["text"])
                received.append(payload)
                if failure == "timeout":
                    raise TimeoutError("indisponível")
                claims = [
                    {"calculation_step": c["calculation_step"], "text": c["text"]}
                    for c in reversed(payload["calculation"]["explanations"])
                ]
                if failure == "changed":
                    claims[0]["text"] = claims[0]["text"].replace("2.500,00", "9.000,00")
                if failure == "omitted":
                    source = payload["evidence"][0]
                    claims = [{"passage_id": source["passage_id"], "text": source["excerpt"]}]
                return {
                    "stopReason": "end_turn",
                    "output": {"message": {"role": "assistant", "content": [{"text": json.dumps({"claims": claims})}]}},
                }

        monkeypatch.setattr(get_settings(), "bedrock_model_id", "test-model")
        monkeypatch.setattr(boto3, "client", lambda *a, **k: Client())
        return received

    return setup


def test_question_calculates_in_code_and_sends_result_and_sources(reader, topic, refund_fact, model):
    received = model()
    result = ask(reader, topic)
    assert result["mode"] == "generated" and result["status"] == "supported"
    calculation = result["calculation"]
    assert calculation["steps"][0]["result_value"] == 2500
    assert "mínimo(R$ 3.000,00; R$ 2.500,00)" in result["claims"][0]["text"]
    assert result["claims"][0]["citations"][0]["version_id"] == str(refund_fact)
    assert result["claims"][0]["calculation_step"] == 0
    assert received[0]["request"]["reference_date"] == result["reference_date"]
    assert received[0]["calculation"]["steps"] == calculation["steps"]
    assert received[0]["calculation"]["assumptions"] == calculation["assumptions"]
    assert reader.get(f"/api/citations/{result['passages'][0]['passage_id']}").status_code == 200
    # Mesmo motor e mesma memória que a rota de regras.
    original = reader.post("/api/regras/ferias/ressarcimento", json={"amount": 3000}).json()
    assert original["assumptions"] == calculation["assumptions"]
    for before, after in zip(original["steps"], calculation["steps"], strict=True):
        assert {k: v for k, v in before.items() if k != "citations"} == {
            k: v for k, v in after.items() if k != "citations"
        }
        for old_source, new_source in zip(before["citations"], after["citations"], strict=True):
            for field in ("passage_id", "version_id", "physical_page", "section", "excerpt"):
                assert old_source[field] == new_source[field]


@pytest.mark.parametrize("failure", ["timeout", "changed", "omitted"])
def test_calculation_fallback_preserves_all_results_sources_and_assumptions(reader, topic, refund_fact, model, failure):
    baseline = ask(reader, topic)
    model(failure)
    fallback = ask(reader, topic)
    assert fallback["notice"]
    assert {k: v for k, v in fallback.items() if k != "notice"} == {k: v for k, v in baseline.items() if k != "notice"}


@pytest.mark.parametrize("restriction", ["expired", "area", "quote", "passage", "failed", "other_topic"])
def test_calculation_requires_eligible_verified_curated_sources(reader, topic, refund_fact, model, restriction):
    received = model()
    updates = {}
    with get_engine().begin() as connection:
        if restriction == "expired":
            connection.execute(
                text("UPDATE document_versions SET valid_until='2026-01-01' WHERE id=:id"), {"id": refund_fact}
            )
        elif restriction == "failed":
            connection.execute(text("UPDATE document_versions SET status='failed' WHERE id=:id"), {"id": refund_fact})
        elif restriction == "quote":
            connection.execute(
                text(
                    "UPDATE fact_citations SET quote='trecho adulterado' WHERE fact_id IN (SELECT id FROM curated_facts WHERE topic_id=:id)"
                ),
                {"id": topic},
            )
        elif restriction == "passage":
            connection.execute(
                text(
                    "UPDATE passages SET excerpt='trecho adulterado' WHERE page_id IN (SELECT id FROM pages WHERE version_id=:id)"
                ),
                {"id": refund_fact},
            )
        elif restriction == "area":
            updates["filters"] = {"area": "INEXISTENTE"}
        elif restriction == "other_topic":
            other = uuid4()
            connection.execute(
                text("INSERT INTO topics(id,name) VALUES (:id,:name)"), {"id": other, "name": str(other)}
            )
            updates["topic_id"] = str(other)
    try:
        result = ask(reader, topic, **updates)
        assert result["status"] == "insufficient" and result["gaps"]
        assert result["calculation"] is None and not result["claims"] and not received
    finally:
        if restriction == "other_topic":
            with get_engine().begin() as connection:
                connection.execute(text("DELETE FROM topics WHERE id=:id"), {"id": other})


@pytest.mark.parametrize(
    "calculation",
    [
        {"rule": "ferias.ressarcimento", "amount": 0},
        {"rule": "ferias.ressarcimento", "amount": 3000, "result_value": 9000},
        {"rule": "ferias.ressarcimento", "team_size": 9},
        {"rule": "inexistente", "amount": 3000},
    ],
)
def test_client_cannot_supply_calculated_results_or_invalid_parameters(reader, topic, calculation):
    response = reader.post(
        "/perguntar", json={"topic_id": str(topic), "question": "Explique", "calculation": calculation}
    )
    assert response.status_code == 422


@pytest.mark.parametrize("perspective", ["deadline", "value", "obligation", "risk"])
def test_explicit_calculation_ignores_search_perspective(reader, topic, refund_fact, model, perspective):
    baseline = ask(reader, topic)
    received = model()
    result = ask(reader, topic, perspective=perspective)
    assert result["mode"] == "generated" and result["status"] == "supported"
    assert result["calculation"] == baseline["calculation"]
    assert result["claims"] == baseline["claims"]
    assert result["passages"] == baseline["passages"]
    assert not result["gaps"] and len(received) == 1
