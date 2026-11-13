from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_identity
from app.contracts import (
    AmountRequest,
    APIError,
    RuleResult,
    TeamAbsenceRequest,
    UnjustifiedAbsencesRequest,
    VacationScheduleRequest,
)
from app.db import get_engine
from app.fatos.repositorio import facts_by_key
from app.regras import ferias, inovacao
from app.regras.base import MissingFacts

router = APIRouter(
    tags=["rules"],
    dependencies=[Depends(current_identity)],
    responses={409: {"model": APIError, "description": "Fatos necessários ao cálculo ainda não foram curados"}},
)


def _run(keys: list[str], rule: Callable[[dict], RuleResult]) -> RuleResult:
    with get_engine().connect() as connection:
        facts = facts_by_key(connection, keys)
    try:
        return rule(facts)
    except MissingFacts as exc:
        raise HTTPException(409, f"Fatos ainda não curados: {', '.join(exc.keys)}.") from exc


@router.post("/ferias/calcular", response_model=RuleResult)
@router.post("/api/regras/ferias/prazos", response_model=RuleResult)
def vacation_schedule(body: VacationScheduleRequest):
    return _run(ferias.SCHEDULE_KEYS, lambda facts: ferias.vacation_schedule(facts, body))


@router.post("/api/regras/ferias/ausencia-simultanea", response_model=RuleResult)
def simultaneous_absence(body: TeamAbsenceRequest):
    return _run(ferias.ABSENCE_KEYS, lambda facts: ferias.simultaneous_absence(facts, body.team_size))


@router.post("/api/regras/ferias/dias-por-faltas", response_model=RuleResult)
def vacation_days(body: UnjustifiedAbsencesRequest):
    return _run(ferias.UNJUSTIFIED_KEYS, lambda facts: ferias.vacation_days_by_absences(facts, body.absences))


@router.post("/api/regras/ferias/ressarcimento", response_model=RuleResult)
def reimbursement(body: AmountRequest):
    return _run(ferias.REIMBURSEMENT_KEYS, lambda facts: ferias.reimbursement(facts, body.amount))


@router.post("/api/regras/inovacao/alcada", response_model=RuleResult)
def approval_authority(body: AmountRequest):
    return _run(inovacao.APPROVAL_KEYS, lambda facts: inovacao.approval_authority(facts, body.amount))


@router.get("/api/regras/inovacao/orcamento", response_model=RuleResult)
def budget():
    return _run(inovacao.BUDGET_KEYS, inovacao.budget_breakdown)


@router.get("/api/regras/inovacao/pagamento-premiacao", response_model=RuleResult)
def prize_payment():
    return _run(inovacao.PAYMENT_KEYS, inovacao.prize_payment_deadline)
