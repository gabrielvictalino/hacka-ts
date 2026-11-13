from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.contracts import Citation, CuratedFact, RuleStep


class MissingFacts(LookupError):
    """Os parâmetros da regra vêm de fatos curados; sem eles o cálculo não é demonstrável."""

    def __init__(self, keys: list[str]):
        super().__init__(", ".join(keys))
        self.keys = keys


def require(facts: dict[str, CuratedFact], keys: list[str]) -> None:
    missing = [key for key in keys if key not in facts]
    if missing:
        raise MissingFacts(missing)


def number(facts: dict[str, CuratedFact], key: str) -> Decimal:
    return Decimal(str(facts[key].value))


def days(facts: dict[str, CuratedFact], key: str) -> int:
    return int(number(facts, key))


def citations(facts: dict[str, CuratedFact], keys: list[str]) -> list[Citation]:
    seen, result = set(), []
    for key in keys:
        for citation in facts[key].citations:
            if citation.passage_id not in seen:
                seen.add(citation.passage_id)
                result.append(citation)
    return result


def step(facts, keys, **values) -> RuleStep:
    return RuleStep(fact_keys=keys, citations=citations(facts, keys), **values)


def br_date(value: date) -> str:
    return f"{value:%d/%m/%Y}"


WEEKDAYS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")


def br_weekday(value: date) -> str:
    return f"{br_date(value)} ({WEEKDAYS[value.weekday()]})"


def money(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    integer, cents = f"{quantized:.2f}".split(".")
    return f"R$ {int(integer):,}".replace(",", ".") + f",{cents}"


def to_money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class BusinessCalendar:
    """Dia útil é o que não é sábado, domingo ou feriado informado (NG_111, item 3.7)."""

    def __init__(self, holidays: list[date] | None = None):
        self.holidays = frozenset(holidays or [])

    def is_business_day(self, value: date) -> bool:
        return value.weekday() < 5 and value not in self.holidays

    def previous_business_day(self, value: date) -> date:
        while not self.is_business_day(value):
            value -= timedelta(days=1)
        return value

    def add_business_days(self, value: date, count: int) -> date:
        while count:
            value += timedelta(days=1)
            if self.is_business_day(value):
                count -= 1
        return value
