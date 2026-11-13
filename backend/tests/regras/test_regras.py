from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from app.config import DemoAccount, get_settings
from app.contracts import Citation, CuratedFact, VacationScheduleRequest
from app.fatos.catalogo import CATALOG
from app.main import app
from app.regras import ferias, inovacao
from app.regras.base import BusinessCalendar, MissingFacts, citations, money
from fastapi.testclient import TestClient
from pydantic import SecretStr


def as_published(fact) -> CuratedFact:
    return CuratedFact(
        id=uuid4(),
        key=fact.key,
        topic_id=uuid4(),
        topic=fact.topic,
        category=fact.category,
        attribute=fact.attribute,
        area=fact.area,
        statement=fact.statement,
        responsible=fact.responsible,
        value=float(fact.value) if fact.value is not None else None,
        value_text=fact.value_text,
        unit=fact.unit,
        starts_on=fact.starts_on,
        ends_on=fact.ends_on,
        conditions=fact.conditions,
        tags=list(fact.tags),
        curated_by="teste",
        curated_at=datetime.now(timezone.utc),
        citations=[
            Citation(
                version_id=uuid5(NAMESPACE_URL, f"{source.code}/{source.version}"),
                # Como no banco, fontes do mesmo item e página resolvem a mesma passagem.
                passage_id=uuid5(NAMESPACE_URL, f"{source.code}/{source.version}/{source.page}/{source.item}"),
                title=source.code,
                code=source.code,
                version=source.version,
                physical_page=source.page,
                excerpt=source.quote,
                section=source.item,
            )
            for source in fact.sources
        ],
    )


FACTS = {fact.key: as_published(fact) for fact in CATALOG}


def by_label(result):
    return {item.label: item for item in result.steps}


def test_vacation_schedule_matches_worked_example_of_ng_111():
    # NG_111 v3.0.0, Anexo C, Exemplo 1: início na quarta-feira 05/05/2027.
    result = ferias.vacation_schedule(FACTS, VacationScheduleRequest(start_date=date(2027, 5, 5)))
    steps = by_label(result)
    assert steps["Solicitação"].result_date == date(2027, 3, 21)
    assert steps["Emissão do aviso pela GGC"].result_date == date(2027, 3, 31)
    assert steps["Assinatura do aviso"].result_date == date(2027, 4, 5)
    payment = steps["Pagamento"]
    assert payment.result_date == date(2027, 4, 30)
    assert payment.computation == [
        "05/05/2027 − 3 dias corridos = 02/05/2027 (domingo)",
        "Dia não útil: antecipado para o dia útil anterior, 30/04/2027 (sexta-feira)",
    ]
    assert steps["Alteração ou cancelamento por iniciativa do empregado"].result_date == date(2027, 4, 15)
    assert result.warnings == []
    assert all(item.citations for item in result.steps)
    assert {c.section for c in steps["Solicitação"].citations} >= {"4.3.1", "4.5.1"}
    assert result.assumptions


def test_vacation_schedule_flags_blocked_start_late_request_and_uses_receipt_and_holidays():
    request = VacationScheduleRequest(
        start_date=date(2027, 5, 6),  # quinta-feira: antecede o descanso semanal
        request_registered_on=date(2027, 4, 1),
        notice_received_on=date(2027, 4, 1),
        holidays=[date(2027, 4, 2)],
    )
    result = ferias.vacation_schedule(FACTS, request)
    steps = by_label(result)
    assert steps["Início de gozo"].result_text == "Dia vedado"
    assert any("4.3.2" in warning for warning in result.warnings)
    assert any("4.3.3" in warning for warning in result.warnings)
    assert steps["Decisão do gestor imediato"].result_date == date(2027, 4, 8)
    # 08/04 (quinta) + 3 dias úteis = 13/04 (terça).
    assert steps["Decisão do diretor da área, se o gestor não decidir"].result_date == date(2027, 4, 13)
    # 01/04 + 5 dias úteis, pulando o feriado de 02/04 e o fim de semana = 09/04; limite D-30 = 06/04.
    assert steps["Assinatura do aviso"].result_date == date(2027, 4, 6)


def test_payment_moves_back_over_informed_holiday():
    result = ferias.vacation_schedule(
        FACTS, VacationScheduleRequest(start_date=date(2027, 5, 10), holidays=[date(2027, 5, 7)])
    )
    # 10/05 − 3 = 07/05 (feriado informado) → 06/05.
    assert by_label(result)["Pagamento"].result_date == date(2027, 5, 6)


@pytest.mark.parametrize(("size", "allowed"), [(1, 1), (3, 1), (4, 1), (6, 1), (7, 2), (9, 2), (10, 3), (14, 4)])
def test_simultaneous_absence_follows_table_4(size, allowed):
    step = ferias.simultaneous_absence(FACTS, size).steps[0]
    assert step.result_value == allowed


def test_simultaneous_absence_shows_rounding():
    assert ferias.simultaneous_absence(FACTS, 9).steps[0].computation[:2] == [
        "30% × 9 = 2,7",
        "Arredondado para baixo: 2",
    ]


@pytest.mark.parametrize(
    ("absences", "expected"),
    [(0, "30 dias corridos"), (5, "30 dias corridos"), (6, "24 dias corridos"), (23, "18 dias corridos")]
    + [(32, "12 dias corridos"), (33, "Perda do direito no período")],
)
def test_vacation_days_by_unjustified_absences(absences, expected):
    assert ferias.vacation_days_by_absences(FACTS, absences).steps[0].result_text == expected


@pytest.mark.parametrize(("expense", "refund"), [(1800, "R$ 1.800,00"), (3000, "R$ 2.500,00"), (2500, "R$ 2.500,00")])
def test_reimbursement_is_capped_per_event(expense, refund):
    assert ferias.reimbursement(FACTS, expense).steps[0].result_text == refund


@pytest.mark.parametrize(
    ("amount", "authority"),
    [
        (18000.00, "Gerente do NIN"),
        (18000.01, "Diretor da DIRTEC"),
        (120000.00, "Diretor da DIRTEC"),
        (120000.01, "Comitê de Alçadas"),
    ],
)
def test_approval_authority_boundaries_from_nt_2026_021(amount, authority):
    assert inovacao.approval_authority(FACTS, amount).steps[0].result_text == authority


def test_budget_separates_total_from_prizes_and_reconciles_items():
    result = inovacao.budget_breakdown(FACTS)
    steps = by_label(result)
    assert result.warnings == []
    assert steps["Orçamento total da edição 2027"].result_value == 96000
    assert steps["Premiação por colocação"].result_value == 16000
    assert steps["Premiação por arena"].computation == ["4 arenas × R$ 2.000,00 = R$ 8.000,00"]
    prizes = steps["Premiações dentro do orçamento total"]
    assert prizes.result_value == 24000
    assert "R$ 24.000,00 ÷ R$ 96.000,00 = 25,0% do orçamento total" in prizes.computation
    assert "Demais itens: R$ 96.000,00 − R$ 24.000,00 = R$ 72.000,00" in prizes.computation
    # Mesmos percentuais da memória de cálculo da NT (Anexo B).
    assert [
        steps[label].result_text
        for label in ("Participação: imersão", "Participação: comunicação", "Participação: kits de prototipagem")
    ] == [
        "31,3%",
        "6,3%",
        "37,5%",
    ]


def test_budget_reports_inconsistent_sources_instead_of_hiding_them():
    facts = dict(FACTS)
    facts["inovacao.orcamento.premiacoes"] = FACTS["inovacao.orcamento.premiacoes"].model_copy(update={"value": 25000})
    assert any("difere do valor declarado" in warning for warning in inovacao.budget_breakdown(facts).warnings)


def test_prize_payment_deadline():
    step = inovacao.prize_payment_deadline(FACTS).steps[0]
    assert step.result_date == date(2027, 7, 30)


def test_rules_require_curated_facts():
    facts = {key: value for key, value in FACTS.items() if key != "ferias.aviso.emissao"}
    with pytest.raises(MissingFacts) as error:
        ferias.vacation_schedule(facts, VacationScheduleRequest(start_date=date(2027, 5, 5)))
    assert error.value.keys == ["ferias.aviso.emissao"]


def test_business_calendar_and_money_format():
    calendar = BusinessCalendar([date(2027, 4, 2)])
    assert calendar.add_business_days(date(2027, 4, 1), 1) == date(2027, 4, 5)
    assert calendar.previous_business_day(date(2027, 4, 4)) == date(2027, 4, 1)
    assert money(Decimal("1234567.89")) == "R$ 1.234.567,89"


@pytest.fixture
def client(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_demo_enabled", True)
    monkeypatch.setattr(settings, "auth_demo_sso_secret", SecretStr("s" * 32))
    monkeypatch.setattr(settings, "auth_cookie_secure", False)
    monkeypatch.setattr(settings, "auth_demo_users", {"reader": DemoAccount(name="L", groups=["clause-empregados"])})
    with TestClient(app) as client:
        yield client


def test_rule_routes_require_session_and_curated_facts(client, monkeypatch):
    assert client.post("/ferias/calcular", json={"start_date": "2027-05-05"}).status_code == 401
    assert client.post("/api/auth/demo/session", json={"user_id": "reader"}).status_code == 200
    monkeypatch.setattr("app.regras.api.facts_by_key", lambda connection, keys: {})
    response = client.post("/ferias/calcular", json={"start_date": "2027-05-05"})
    assert response.status_code == 409
    assert "ferias.solicitacao.antecedencia" in response.json()["detail"]
    monkeypatch.setattr("app.regras.api.facts_by_key", lambda connection, keys: {key: FACTS[key] for key in keys})
    response = client.post("/api/regras/inovacao/alcada", json={"amount": 18000.01})
    assert response.status_code == 200
    assert response.json()["steps"][0]["result_text"] == "Diretor da DIRTEC"
    assert client.post("/api/regras/ferias/ausencia-simultanea", json={"team_size": 0}).status_code == 422


def all_results():
    return [
        ferias.vacation_schedule(
            FACTS,
            VacationScheduleRequest(
                start_date=date(2027, 5, 5),
                request_registered_on=date(2027, 3, 1),
                notice_received_on=date(2027, 3, 31),
            ),
        ),
        ferias.simultaneous_absence(FACTS, 9),
        ferias.vacation_days_by_absences(FACTS, 3),
        ferias.reimbursement(FACTS, 100),
        inovacao.approval_authority(FACTS, 1),
        inovacao.budget_breakdown(FACTS),
        inovacao.prize_payment_deadline(FACTS),
    ]


def test_every_parameter_keeps_its_evidence_in_the_demonstration():
    for result in all_results():
        for item in result.steps:
            for key in item.fact_keys:
                for source in FACTS[key].citations:
                    assert any(
                        kept.passage_id == source.passage_id and source.excerpt in kept.excerpt
                        for kept in item.citations
                    ), f"{result.rule} · {item.label}: falta {source.excerpt!r} de {key}"


def test_budget_total_cites_each_summed_line_of_the_same_table():
    total = by_label(inovacao.budget_breakdown(FACTS))["Orçamento total da edição 2027"]
    excerpts = [citation.excerpt for citation in total.citations]
    for line in (
        "Premiação por colocação (8.000 + 5.000 + 3.000) 16.000,00",
        "Premiação por arena (4 × 2.000) 8.000,00",
        "Imersão 30.000,00",
        "Kits de prototipagem 36.000,00",
        "Comunicação 6.000,00",
        "Total 96.000,00",
    ):
        assert line in excerpts
    assert len({citation.passage_id for citation in total.citations if citation.section == "3"}) == 1


def test_citations_drop_only_repeated_or_contained_excerpts():
    base = FACTS["ferias.aviso.assinatura_recebimento"]
    wide = base.citations[0]
    narrow = wide.model_copy(update={"excerpt": "nunca depois de 30 dias antes do início de gozo."})
    other = wide.model_copy(update={"excerpt": "Assinatura do aviso pelo empregado"})
    sibling = wide.model_copy(update={"excerpt": "outro recorte da mesma passagem"})

    def facts(*groups):
        return {str(i): base.model_copy(update={"citations": list(group)}) for i, group in enumerate(groups)}

    assert citations(facts([wide], [wide]), ["0", "1"]) == [wide]
    assert citations(facts([wide], [narrow]), ["0", "1"]) == [wide]
    assert citations(facts([narrow], [other], [wide]), ["0", "1", "2"]) == [wide]
    assert citations(facts([wide], [sibling]), ["0", "1"]) == [wide, sibling]
