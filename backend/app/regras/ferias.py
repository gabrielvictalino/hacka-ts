"""Regras de Férias calculadas em código a partir dos fatos curados da NG_111 v3.0.0 e documentos de apoio."""

from datetime import timedelta
from decimal import ROUND_FLOOR, Decimal

from app.contracts import CuratedFact, RuleResult, VacationScheduleRequest
from app.regras.base import BusinessCalendar, br_date, br_weekday, days, money, number, require, step, to_money

SCHEDULE_KEYS = [
    "ferias.solicitacao.antecedencia",
    "ferias.inicio.dia_vedado",
    "ferias.decisao.gestor",
    "ferias.decisao.diretor",
    "ferias.aviso.emissao",
    "ferias.aviso.assinatura_recebimento",
    "ferias.aviso.assinatura_limite",
    "ferias.pagamento.antecedencia",
    "ferias.alteracao.iniciativa_empregado",
    "ferias.alteracao.necessidade_servico",
]
ABSENCE_KEYS = ["ferias.ausencia.percentual"]
# Limites das faixas da Tabela 1 do TB_1111-001; os dias de cada faixa vêm dos fatos curados.
ABSENCE_BANDS = ((0, 5, "ferias.faltas.faixa_1"), (6, 14, "ferias.faltas.faixa_2"), (15, 23, "ferias.faltas.faixa_3"))
ABSENCE_BANDS += ((24, 32, "ferias.faltas.faixa_4"), (33, None, "ferias.faltas.faixa_5"))
UNJUSTIFIED_KEYS = [key for _, _, key in ABSENCE_BANDS]
REIMBURSEMENT_KEYS = ["ferias.ressarcimento.limite"]

CALENDAR_ASSUMPTION = (
    "Dias úteis excluem sábados, domingos e os feriados informados na consulta; "
    "o acervo não traz o calendário de feriados da sede (NG_111, item 3.7)."
)


def vacation_schedule(facts: dict[str, CuratedFact], request: VacationScheduleRequest) -> RuleResult:
    require(facts, SCHEDULE_KEYS)
    calendar = BusinessCalendar(request.holidays)
    start = request.start_date
    steps, warnings = [], []

    def before(key: str):
        offset = days(facts, key)
        return offset, start - timedelta(days=offset)

    blocked_days = days(facts, "ferias.inicio.dia_vedado")
    following = [start + timedelta(days=offset) for offset in range(1, blocked_days + 1)]
    non_business = [value for value in following if not calendar.is_business_day(value)]
    computation = [f"D = {br_weekday(start)}"]
    if not calendar.is_business_day(start):
        warnings.append(f"O início de gozo {br_date(start)} não é dia útil (NG_111, item 4.3.2).")
        computation.append(f"{br_date(start)} não é dia útil.")
    elif non_business:
        warnings.append(
            f"O início de gozo {br_date(start)} cai nos {blocked_days} dias úteis que antecedem "
            f"{br_weekday(non_business[0])}, dia não útil (NG_111, item 4.3.2)."
        )
        computation.append(f"Próximo dia não útil em até {blocked_days} dias: {br_weekday(non_business[0])}.")
    else:
        computation.append(f"Os {blocked_days} dias seguintes são úteis; o início não é dia vedado.")
    steps.append(
        step(
            facts,
            ["ferias.inicio.dia_vedado"],
            label="Início de gozo",
            rule=facts["ferias.inicio.dia_vedado"].value_text,
            result_text="Dia vedado" if warnings else "Data permitida",
            result_date=start,
            computation=computation,
        )
    )

    offset, deadline = before("ferias.solicitacao.antecedencia")
    computation = [f"{br_date(start)} − {offset} dias corridos = {br_weekday(deadline)}"]
    if request.request_registered_on and request.request_registered_on > deadline:
        warnings.append(
            f"Solicitação registrada em {br_date(request.request_registered_on)}, depois de D-{offset} "
            f"({br_date(deadline)}): só é aceita por decisão do diretor da área (NG_111, item 4.3.3)."
        )
        computation.append(f"Registro em {br_date(request.request_registered_on)} > {br_date(deadline)}.")
    steps.append(
        step(
            facts,
            ["ferias.solicitacao.antecedencia"],
            label="Solicitação",
            rule=facts["ferias.solicitacao.antecedencia"].value_text,
            result_text=br_date(deadline),
            result_date=deadline,
            computation=computation,
        )
    )

    if request.request_registered_on:
        registered = request.request_registered_on
        manager_days = days(facts, "ferias.decisao.gestor")
        manager_deadline = registered + timedelta(days=manager_days)
        steps.append(
            step(
                facts,
                ["ferias.decisao.gestor"],
                label="Decisão do gestor imediato",
                rule=facts["ferias.decisao.gestor"].value_text,
                result_text=br_date(manager_deadline),
                result_date=manager_deadline,
                computation=[f"{br_date(registered)} + {manager_days} dias corridos = {br_weekday(manager_deadline)}"],
            )
        )
        director_days = days(facts, "ferias.decisao.diretor")
        director_deadline = calendar.add_business_days(manager_deadline, director_days)
        steps.append(
            step(
                facts,
                ["ferias.decisao.gestor", "ferias.decisao.diretor"],
                label="Decisão do diretor da área, se o gestor não decidir",
                rule=facts["ferias.decisao.diretor"].value_text,
                result_text=br_date(director_deadline),
                result_date=director_deadline,
                computation=[
                    f"Escalonamento após {br_date(manager_deadline)} sem decisão do gestor.",
                    f"{br_date(manager_deadline)} + {director_days} dias úteis = {br_weekday(director_deadline)}",
                ],
            )
        )

    offset, notice = before("ferias.aviso.emissao")
    steps.append(
        step(
            facts,
            ["ferias.aviso.emissao"],
            label="Emissão do aviso pela GGC",
            rule=facts["ferias.aviso.emissao"].value_text,
            result_text=br_date(notice),
            result_date=notice,
            computation=[f"{br_date(start)} − {offset} dias corridos = {br_weekday(notice)}"],
        )
    )

    limit_offset, signature_limit = before("ferias.aviso.assinatura_limite")
    computation = [f"Limite: {br_date(start)} − {limit_offset} dias corridos = {br_weekday(signature_limit)}"]
    signature = signature_limit
    if request.notice_received_on:
        received = request.notice_received_on
        business_days = days(facts, "ferias.aviso.assinatura_recebimento")
        by_receipt = calendar.add_business_days(received, business_days)
        signature = min(by_receipt, signature_limit)
        computation.append(f"Recebimento: {br_date(received)} + {business_days} dias úteis = {br_weekday(by_receipt)}")
        computation.append(f"Vale a data mais cedo: {br_date(signature)}")
        if received > signature_limit:
            warnings.append(
                f"Aviso recebido em {br_date(received)}, depois de D-{limit_offset}: "
                "as férias não podem ser iniciadas sem aviso assinado (PX_1111-001, item 8.5.2)."
            )
    steps.append(
        step(
            facts,
            ["ferias.aviso.assinatura_recebimento", "ferias.aviso.assinatura_limite"],
            label="Assinatura do aviso",
            rule=f"{facts['ferias.aviso.assinatura_recebimento'].value_text}; "
            f"{facts['ferias.aviso.assinatura_limite'].value_text.lower()}",
            result_text=br_date(signature),
            result_date=signature,
            computation=computation,
        )
    )

    offset, payment = before("ferias.pagamento.antecedencia")
    adjusted = calendar.previous_business_day(payment)
    computation = [f"{br_date(start)} − {offset} dias corridos = {br_weekday(payment)}"]
    if adjusted != payment:
        computation.append(f"Dia não útil: antecipado para o dia útil anterior, {br_weekday(adjusted)}")
    steps.append(
        step(
            facts,
            ["ferias.pagamento.antecedencia"],
            label="Pagamento",
            rule=f"{facts['ferias.pagamento.antecedencia'].value_text}; "
            f"{facts['ferias.pagamento.antecedencia'].conditions}",
            result_text=br_date(adjusted),
            result_date=adjusted,
            computation=computation,
        )
    )

    offset, change = before("ferias.alteracao.iniciativa_empregado")
    steps.append(
        step(
            facts,
            ["ferias.alteracao.iniciativa_empregado"],
            label="Alteração ou cancelamento por iniciativa do empregado",
            rule=facts["ferias.alteracao.iniciativa_empregado"].value_text,
            result_text=br_date(change),
            result_date=change,
            computation=[f"{br_date(start)} − {offset} dias corridos = {br_weekday(change)}"],
        )
    )
    offset, service = before("ferias.alteracao.necessidade_servico")
    steps.append(
        step(
            facts,
            ["ferias.alteracao.necessidade_servico"],
            label="Alteração somente por necessidade de serviço",
            rule=facts["ferias.alteracao.necessidade_servico"].value_text,
            result_text=f"A partir de {br_date(service)}",
            result_date=service,
            computation=[f"{br_date(start)} − {offset} dias corridos = {br_weekday(service)}"],
        )
    )
    return RuleResult(rule="ferias.prazos", steps=steps, warnings=warnings, assumptions=[CALENDAR_ASSUMPTION])


def simultaneous_absence(facts: dict[str, CuratedFact], team_size: int) -> RuleResult:
    require(facts, ABSENCE_KEYS)
    percent = number(facts, "ferias.ausencia.percentual")
    raw = Decimal(team_size) * percent / 100
    floor = int(raw.to_integral_value(rounding=ROUND_FLOOR))
    allowed = max(floor, 1)
    computation = [
        f"{percent.normalize():f}% × {team_size} = {raw.normalize():f}".replace(".", ","),
        f"Arredondado para baixo: {floor}",
    ]
    if team_size <= 3 or floor < 1:
        computation.append("Equipe de até 3 empregados ou resultado menor que 1: uma pessoa por vez.")
    return RuleResult(
        rule="ferias.ausencia_simultanea",
        steps=[
            step(
                facts,
                ABSENCE_KEYS,
                label="Máximo de pessoas de férias ao mesmo tempo",
                rule=facts["ferias.ausencia.percentual"].conditions,
                result_text=f"{allowed} {'pessoa' if allowed == 1 else 'pessoas'}",
                result_value=allowed,
                computation=computation,
            )
        ],
    )


def vacation_days_by_absences(facts: dict[str, CuratedFact], absences: int) -> RuleResult:
    require(facts, UNJUSTIFIED_KEYS)
    lower, upper, key = next(band for band in ABSENCE_BANDS if band[1] is None or absences <= band[1])
    fact = facts[key]
    band = f"{lower} a {upper}" if upper is not None else f"mais de {lower - 1}"
    return RuleResult(
        rule="ferias.dias_por_faltas",
        steps=[
            step(
                facts,
                [key],
                label="Dias de férias no período aquisitivo",
                rule="Tabela 1 do TB_1111-001: faltas injustificadas × dias corridos de férias",
                result_text=fact.value_text,
                result_value=fact.value,
                computation=[f"{absences} faltas injustificadas → faixa {band} → {fact.value_text}"],
            )
        ],
    )


def reimbursement(facts: dict[str, CuratedFact], amount: float) -> RuleResult:
    require(facts, REIMBURSEMENT_KEYS)
    expenses = to_money(amount)
    limit = to_money(number(facts, "ferias.ressarcimento.limite"))
    refunded = min(expenses, limit)
    comparison = "dentro do" if expenses <= limit else "acima do"
    return RuleResult(
        rule="ferias.ressarcimento",
        steps=[
            step(
                facts,
                REIMBURSEMENT_KEYS,
                label="Ressarcimento por alteração por necessidade de serviço",
                rule=facts["ferias.ressarcimento.limite"].value_text,
                result_text=money(refunded),
                result_value=float(refunded),
                computation=[
                    f"Despesa comprovada {money(expenses)} {comparison} limite de {money(limit)} por evento",
                    f"Ressarcimento = mínimo({money(expenses)}; {money(limit)}) = {money(refunded)}",
                ],
            )
        ],
        assumptions=[facts["ferias.ressarcimento.limite"].conditions],
    )
