from datetime import date
from uuid import uuid4

import pytest
from app import questions
from app.auth import current_identity
from app.config import get_settings
from app.contracts import Claim
from app.db import get_engine
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


def ingest(topic, texts):
    content = make_pdf(texts)
    with get_engine().begin() as connection:
        version = enqueue(connection, topic, "fonte.pdf", content).version_id
    assert process_one()
    return version, content


def ask(reader, topic, question, **kwargs):
    response = reader.post("/perguntar", json={"topic_id": str(topic), "question": question, **kwargs})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    ("question", "literal", "status"),
    [
        ("Qual o prazo de férias?", "1. Férias: prazo de solicitação de 30 dias corridos para GGC.", "partial"),
        ("Qual o prazo de inovação?", "2. Inovação: prazo de inscrição de 15 dias úteis para GGC.", "partial"),
        (
            "Qual o valor de locação?",
            "CLÁUSULA PRIMEIRA - Locação: valor de R$ 2.000,00 por mês para GGC.",
            "supported",
        ),
    ],
)
def test_topics_literal_physical_page_and_stable_evidence(reader, topic, question, literal, status):
    version, content = ingest(topic, ["", literal])
    result = ask(reader, topic, question)
    assert result["mode"] == "extractive" and result["status"] == status
    citation = result["passages"][0]
    assert citation["physical_page"] == 2 and citation["excerpt"] == literal
    assert citation["version_id"] == str(version)
    assert citation["document_id"] and citation["section"]
    assert reader.get(f"/api/citations/{citation['passage_id']}").json() == citation
    assert reader.get(f"/api/documents/{version}/file").content == content
    assert reader.post("/api/questions", json={"topic_id": str(topic), "question": question}).json() == result


def test_gaps_partial_and_no_external_completion(reader, topic):
    ingest(topic, ["Férias: prazo de 30 dias corridos."])
    result = ask(reader, topic, "Qual o prazo de férias? Qual o valor do auxílio marciano?")
    assert result["status"] == "partial" and len(result["gaps"]) == 1
    assert "auxílio marciano" in result["gaps"][0]
    assert all("marciano" not in claim["text"] for claim in result["claims"])
    missing = ask(reader, topic, "Qual o auxílio marciano?")
    assert missing["status"] == "insufficient" and not missing["claims"]
    assert "Não consta" in missing["gaps"][0]
    # Um termo comum não confirma a pergunta inteira.
    assert ask(reader, topic, "Férias marcianas")["status"] == "partial"


def test_filters_and_perspectives_are_applied(reader, topic):
    ingest(topic, ["1. Férias: prazo de 30 dias para GGC.\n2. Férias: valor de R$ 500 para FIN."])
    deadlines = ask(reader, topic, "Férias", perspective="deadline", filters={"area": "GGC"})
    assert len(deadlines["passages"]) == 1 and "30 dias" in deadlines["passages"][0]["excerpt"]
    values = ask(reader, topic, "Férias", perspective="value", filters={"area": "FIN"})
    assert len(values["passages"]) == 1 and "500" in values["passages"][0]["excerpt"]
    assert ask(reader, topic, "Férias", filters={"area": "INEXISTENTE"})["status"] == "insufficient"


def test_eligibility_and_successor_keep_old_citation(reader, topic):
    old, content = ingest(
        topic,
        [
            "Título: Férias\nSigla e Número: NG_777\nVersão: 2.0.0\nFase: Vigente\nVigência: 01/01/2025 a 31/12/2027",
            "1. Férias: prazo de 45 dias.",
        ],
    )
    first = ask(reader, topic, "Prazo de férias", reference_date="2026-07-01")
    citation = next(c for c in first["passages"] if c["physical_page"] == 2)
    new, _ = ingest(
        topic,
        [
            "Título: Férias\nSigla e Número: NG_777\nVersão: 3.0.0\nFase: Vigente\n"
            "Vigência: 03/08/2026 a 31/12/2028\nSubstitui a v2",
            "1. Férias: prazo de 30 dias.",
        ],
    )
    current = ask(reader, topic, "Prazo de férias", reference_date="2026-11-12")
    assert {c["version_id"] for c in current["passages"]} == {str(new)}
    historic = ask(reader, topic, "Prazo de férias em 01/07/2026")
    assert historic["reference_date"] == "2026-07-01"
    assert {c["version_id"] for c in historic["passages"]} == {str(old)}
    assert reader.get(f"/api/citations/{citation['passage_id']}").json() == citation
    assert reader.get(f"/api/documents/{old}/file").content == content
    assert ask(reader, topic, "Prazo de férias", reference_date="2029-01-01")["status"] == "insufficient"


def test_only_ready_versions_in_selected_topic(reader, topic):
    version, _ = ingest(topic, ["Férias: prazo de 30 dias."])
    with get_engine().begin() as connection:
        connection.execute(text("UPDATE document_versions SET status='processing' WHERE id=:id"), {"id": version})
    assert ask(reader, topic, "Prazo férias")["status"] == "insufficient"
    with get_engine().begin() as connection:
        connection.execute(text("UPDATE document_versions SET status='ready' WHERE id=:id"), {"id": version})
    with get_engine().connect() as connection:
        assert questions.eligible_versions(connection, uuid4(), date(2026, 11, 12)) == []


@pytest.mark.parametrize(
    "failure", [TimeoutError("expirou"), RuntimeError("indisponível"), ValueError("saída inválida")]
)
def test_bedrock_contingency_keeps_identical_evidence(reader, topic, monkeypatch, failure):
    ingest(topic, ["Locação: prazo de 30 dias."])
    baseline = ask(reader, topic, "Prazo locação")
    monkeypatch.setattr(get_settings(), "bedrock_model_id", "test-model")

    def fail(*args):
        raise failure

    monkeypatch.setattr(questions, "generate_claims", fail)
    fallback = ask(reader, topic, "Prazo locação")
    assert fallback["mode"] == "extractive" and fallback["notice"]
    assert {k: v for k, v in fallback.items() if k != "notice"} == {k: v for k, v in baseline.items() if k != "notice"}


@pytest.mark.parametrize(
    "output",
    [
        '{"claims":[{"passage_id":"inventado","text":"30 dias"}]}',
        '{"claims":[]}',
        '{"claims":[{"passage_id":"REAL","text":"999 dias"}]}',
        '{"claims":[{"passage_id":"REAL","text":"30 dias"}]}',
        "não é JSON",
    ],
)
def test_bedrock_output_is_verified_against_literals(reader, topic, monkeypatch, output):
    import boto3

    ingest(topic, ["Locação: prazo de 30 dias."])
    baseline = ask(reader, topic, "Prazo locação")
    output = output.replace("REAL", baseline["passages"][0]["passage_id"])

    class Model:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def converse(self, **kwargs):
            return {"output": {"message": {"content": [{"text": output}]}}}

    monkeypatch.setattr(boto3, "client", lambda *a, **k: Model())
    monkeypatch.setattr(get_settings(), "bedrock_model_id", "test-model")
    assert ask(reader, topic, "Prazo locação")["notice"]


def test_valid_generation_preserves_passages_and_gaps(reader, topic, monkeypatch):
    ingest(topic, ["Locação: prazo de 30 dias."])
    monkeypatch.setattr(get_settings(), "bedrock_model_id", "test-model")
    monkeypatch.setattr(
        questions,
        "generate_claims",
        lambda body, citations: [Claim(text=citations[0].excerpt, citations=[citations[0]])],
    )
    result = ask(reader, topic, "Prazo locação? Valor marciano?")
    assert result["mode"] == "generated" and result["status"] == "partial" and result["gaps"]


def test_validation_and_auth(reader, topic):
    for question in ("", "   "):
        assert reader.post("/perguntar", json={"topic_id": str(topic), "question": question}).status_code == 422
    assert reader.post("/perguntar", json={"topic_id": str(uuid4()), "question": "Prazo?"}).status_code == 404
    assert reader.post("/perguntar", json={"topic_id": str(topic), "question": "Em 31/02/2026?"}).status_code == 422
    assert (
        reader.post("/perguntar", json={"topic_id": str(topic), "question": "Em 2025-01-01 e 2026-01-01?"}).status_code
        == 422
    )
    app.dependency_overrides.clear()
    assert reader.post("/perguntar", json={"topic_id": str(topic), "question": "Prazo?"}).status_code == 401
    assert reader.get(f"/api/citations/{uuid4()}").status_code == 401


def test_citation_mismatch_is_never_displayed(reader, topic):
    ingest(topic, ["Férias: prazo de 30 dias."])
    citation = ask(reader, topic, "Prazo férias")["passages"][0]
    with get_engine().begin() as connection:
        connection.execute(
            text("UPDATE passages SET excerpt='Prazo férias inventado' WHERE id=:id"), {"id": citation["passage_id"]}
        )
    assert ask(reader, topic, "Prazo férias")["status"] == "insufficient"
    assert reader.get(f"/api/citations/{citation['passage_id']}").status_code == 409


def test_bedrock_validates_full_excerpt_and_bounds_network_timeout(reader, topic, monkeypatch):
    import boto3

    ingest(topic, ["Locação: não é permitido prorrogar sem aviso de 30 dias."])
    baseline = ask(reader, topic, "Prazo locação")
    source = baseline["passages"][0]
    monkeypatch.setattr(get_settings(), "bedrock_model_id", "test-model")

    class Model:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def converse(self, **kwargs):
            import json

            assert kwargs["modelId"] == "test-model"
            return {
                "output": {
                    "message": {
                        "content": [
                            {
                                "text": json.dumps(
                                    {"claims": [{"passage_id": source["passage_id"], "text": source["excerpt"]}]}
                                )
                            }
                        ]
                    }
                }
            }

    def model_client(*args, **kwargs):
        assert args == ("bedrock-runtime",)
        assert kwargs["config"].read_timeout == 5
        assert kwargs["config"].connect_timeout == 2
        assert kwargs["config"].retries == {"total_max_attempts": 1}
        return Model()

    monkeypatch.setattr(boto3, "client", model_client)
    result = ask(reader, topic, "Prazo locação")
    assert result["mode"] == "generated" and result["notice"] is None
    assert result["passages"] == baseline["passages"]
    assert "não é permitido" in result["claims"][0]["text"]


def test_too_many_subquestions_are_rejected(reader, topic):
    response = reader.post("/perguntar", json={"topic_id": str(topic), "question": "Prazo?" * 13})
    assert response.status_code == 422


def test_topic_boundary_is_enforced(reader, topic):
    ingest(topic, ["Locação: prazo de 30 dias."])
    other = uuid4()
    with get_engine().begin() as connection:
        connection.execute(text("INSERT INTO topics(id, name) VALUES (:id, :name)"), {"id": other, "name": str(other)})
    try:
        assert ask(reader, other, "Prazo locação")["status"] == "insufficient"
    finally:
        with get_engine().begin() as connection:
            connection.execute(text("DELETE FROM topics WHERE id=:id"), {"id": other})


@pytest.mark.parametrize(
    "declaration",
    [
        "Substitui a NG_111 versão 2.0.0",
        "Substitui a NG_111\nversão 2.0.0",
        "Substitui a versão 2.0.0",
        "Substitui a v2",
    ],
)
def test_historical_previous_phase_with_collection_successor_wording(reader, topic, declaration):
    old, content = ingest(
        topic,
        [
            "Título: Férias\nSigla e Número: NG_111\nVersão: 2.0.0\nFase: Versão anterior\n"
            "Vigência: 10/12/2025 a 10/06/2027",
            "1. Férias: prazo de 30 dias corridos.",
        ],
    )
    new, _ = ingest(
        topic,
        [
            "Título: Férias\nSigla e Número: NG_111\nVersão: 3.0.0\nFase: Vigente\n"
            f"Vigência: 03/08/2026 a 03/02/2028\n{declaration}",
            "1. Férias: prazo de 45 dias corridos.",
        ],
    )
    historical = ask(reader, topic, "Qual o prazo de férias em 10/07/2026?")
    assert historical["status"] == "supported"
    assert {c["version_id"] for c in historical["passages"]} == {str(old)}
    source = historical["passages"][0]
    for reference, expected in (("2026-08-02", old), ("2026-08-03", new), ("2026-11-12", new)):
        result = ask(reader, topic, "Prazo de férias", reference_date=reference)
        assert {c["version_id"] for c in result["passages"]} == {str(expected)}
    assert reader.get(f"/api/citations/{source['passage_id']}").json() == source
    assert reader.get(f"/api/documents/{old}/file").content == content


def test_succession_mentioning_another_code_does_not_replace_version(reader, topic):
    old, _ = ingest(
        topic,
        [
            "Título: Férias\nSigla e Número: NG_111\nVersão: 2.0.0\nFase: Vigente\nVigência: 01/01/2025 a 31/12/2027",
            "Férias: prazo de 30 dias.",
        ],
    )
    new, _ = ingest(
        topic,
        [
            "Título: Férias\nSigla e Número: NG_111\nVersão: 3.0.0\nFase: Vigente\n"
            "Vigência: 03/08/2026 a 31/12/2028\nSubstitui a NG_999 versão 2.0.0",
            "Férias: prazo de 45 dias.",
        ],
    )
    result = ask(reader, topic, "Prazo férias", reference_date="2026-11-12")
    assert {c["version_id"] for c in result["passages"]} == {str(old), str(new)}


@pytest.mark.parametrize(
    "literal",
    [
        "O prazo de férias é de 45 dias. Para cancelar, consulte a GGC.",
        "O prazo de férias é de 45 dias; para cancelar, consulte a GGC.",
        "O prazo para cancelar férias deve ser consultado com a GGC.",
        "O prazo para cancelar férias não consta no acervo; férias duram 45 dias.",
        "O prazo para cancelar férias não foi definido, apesar do aviso de 45 dias.",
    ],
)
def test_related_words_do_not_confirm_unanswered_cancellation_deadline(reader, topic, literal):
    ingest(topic, [literal])
    result = ask(reader, topic, "Qual o prazo para cancelar férias?")
    assert result["status"] == "partial"
    assert result["gaps"] == ["Não consta confirmação completa para: Qual o prazo para cancelar férias."]
    assert result["claims"][0]["text"] == literal


def test_explicit_deadline_for_requested_action_is_supported(reader, topic):
    ingest(topic, ["O prazo para cancelar férias é de 5 dias úteis."])
    result = ask(reader, topic, "Qual o prazo para cancelar férias?")
    assert result["status"] == "supported" and not result["gaps"]


@pytest.fixture
def bedrock_selection(monkeypatch):
    import json

    import boto3

    def configure(citations):
        class Model:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def converse(self, **kwargs):
                payload = {"claims": [{"passage_id": c["passage_id"], "text": c["excerpt"]} for c in citations]}
                return {"output": {"message": {"content": [{"text": json.dumps(payload)}]}}}

        monkeypatch.setattr(boto3, "client", lambda *a, **k: Model())
        monkeypatch.setattr(get_settings(), "bedrock_model_id", "test-model")

    return configure


def test_model_dropping_supported_point_falls_back_to_complete_extractive_answer(reader, topic, bedrock_selection):
    ingest(topic, ["1. Férias: prazo de 30 dias.\n2. Locação: valor de R$ 500 por mês."])
    question = "Qual o prazo de férias? Qual o valor de locação?"
    baseline = ask(reader, topic, question)
    assert baseline["status"] == "supported"
    bedrock_selection([next(c for c in baseline["passages"] if "30 dias" in c["excerpt"])])
    result = ask(reader, topic, question)
    assert result["notice"] and result["mode"] == "extractive"
    assert result["claims"] == baseline["claims"]
    assert result["passages"] == baseline["passages"] and result["gaps"] == baseline["gaps"]


def test_model_retaining_each_supported_point_can_generate(reader, topic, bedrock_selection):
    ingest(topic, ["1. Férias: prazo de 30 dias.\n2. Locação: valor de R$ 500 por mês."])
    question = "Qual o prazo de férias? Qual o valor de locação?"
    baseline = ask(reader, topic, question)
    bedrock_selection(list(reversed(baseline["passages"])))
    result = ask(reader, topic, question)
    assert result["mode"] == "generated" and result["status"] == "supported"
    assert result["notice"] is None and not result["gaps"]
    assert {claim["text"] for claim in result["claims"]} == {claim["text"] for claim in baseline["claims"]}


def test_model_cannot_replace_support_with_merely_related_passage(reader, topic, bedrock_selection):
    ingest(topic, ["1. Férias: prazo de 30 dias.\n2. Para férias, consulte a GGC."])
    baseline = ask(reader, topic, "Qual o prazo de férias?")
    assert baseline["status"] == "supported"
    bedrock_selection([next(c for c in baseline["passages"] if "consulte" in c["excerpt"])])
    result = ask(reader, topic, "Qual o prazo de férias?")
    assert result["mode"] == "extractive" and result["notice"]
    assert result["claims"] == baseline["claims"]


@pytest.mark.parametrize(
    "literal",
    [
        "O prazo para cancelar férias difere dos 45 dias exigidos para solicitar férias.",
        "O prazo para cancelar férias difere de 45 dias.",
        "O prazo para cancelar férias é diferente de 45 dias.",
        "O prazo para cancelar férias não é de 45 dias.",
        "O prazo para cancelar férias será informado após os 45 dias para solicitar férias.",
        "O prazo para cancelar férias é de 45 dias exigidos para solicitar férias.",
    ],
)
def test_other_action_or_comparison_never_supplies_requested_deadline(reader, topic, literal):
    ingest(topic, [literal])
    result = ask(reader, topic, "Qual o prazo para cancelar férias?")
    assert result["status"] == "partial"
    assert result["gaps"]
    assert result["claims"][0]["text"] == literal


@pytest.mark.parametrize(
    "declaration",
    [
        "Esta norma não substitui a NG_111 versão 2.0.0.",
        "Esta norma não\nsubstitui a NG_111 versão 2.0.0.",
        "Esta norma nunca substitui a NG_111 versão 2.0.0.",
        "Não se deve afirmar que esta norma substitui a NG_111 versão 2.0.0.",
        "A afirmação de que esta norma substitui a NG_111 versão 2.0.0 não procede.",
    ],
)
def test_negated_succession_does_not_remove_current_version(reader, topic, declaration):
    old, content = ingest(
        topic,
        [
            "Título: Férias\nSigla e Número: NG_111\nVersão: 2.0.0\nFase: Vigente\nVigência: 01/01/2025 a 31/12/2027",
            "Férias: prazo de 30 dias.",
        ],
    )
    old_source = ask(reader, topic, "Prazo de férias", reference_date="2026-07-10")["passages"][0]
    new, _ = ingest(
        topic,
        [
            "Título: Férias\nSigla e Número: NG_111\nVersão: 3.0.0\nFase: Vigente\n"
            f"Vigência: 03/08/2026 a 31/12/2028\n{declaration}",
            "Férias: prazo de 45 dias.",
        ],
    )
    current = ask(reader, topic, "Prazo de férias", reference_date="2026-11-12")
    assert {c["version_id"] for c in current["passages"]} == {str(old), str(new)}
    assert reader.get(f"/api/citations/{old_source['passage_id']}").json() == old_source
    assert reader.get(f"/api/documents/{old}/file").content == content


@pytest.mark.parametrize(
    ("question", "literal"),
    [
        ("Qual o prazo de solicitação de férias?", "1. Férias: prazo de solicitação de 30 dias corridos para GGC."),
        ("Qual o prazo de inscrição de inovação?", "2. Inovação: prazo de inscrição de 15 dias úteis para GGC."),
        ("Qual o prazo para cancelar férias?", "O prazo para cancelar férias é de 1 mês."),
        ("Qual o prazo para cancelar férias?", "O prazo para cancelar férias será de 5 dias úteis."),
        ("Qual o prazo para cancelar férias?", "Prazo para cancelar férias: 10/12/2026."),
        ("Qual o valor de cancelamento de locação?", "Valor de cancelamento de locação: R$ 500,00."),
    ],
)
def test_direct_quantitative_assignment_matches_requested_subject(reader, topic, question, literal):
    ingest(topic, [literal])
    result = ask(reader, topic, question)
    assert result["status"] == "supported" and not result["gaps"]
    assert result["claims"][0]["text"] == literal


def test_value_of_another_action_does_not_confirm_requested_value(reader, topic):
    ingest(topic, ["O valor de cancelamento de locação difere dos R$ 500,00 exigidos para renovar locação."])
    result = ask(reader, topic, "Qual o valor de cancelamento de locação?")
    assert result["status"] == "partial" and result["gaps"]
