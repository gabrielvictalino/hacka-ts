"""Regras de valores e prazos do Programa Ideias em Campo 2027, calculadas em código a partir dos fatos curados."""

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.contracts import CuratedFact, RuleResult
from app.regras.base import br_date, br_weekday, days, money, number, require, step, to_money

APPROVAL_KEYS = ["inovacao.alcada.gerente_nin", "inovacao.alcada.diretor_dirtec", "inovacao.alcada.comite"]
BUDGET_ITEMS = [
    "inovacao.orcamento.premiacao_colocacao",
    "inovacao.orcamento.premiacao_arena",
    "inovacao.orcamento.imersao",
    "inovacao.orcamento.kits_prototipagem",
    "inovacao.orcamento.comunicacao",
]
PRIZES = ["inovacao.premio.1_lugar", "inovacao.premio.2_lugar", "inovacao.premio.3_lugar"]
BUDGET_KEYS = [
    "inovacao.orcamento.total",
    "inovacao.orcamento.premiacoes",
    *BUDGET_ITEMS,
    *PRIZES,
    "inovacao.premio.arena",
    "inovacao.arenas.quantidade",
]
PAYMENT_KEYS = ["inovacao.edicao_2027.fase_7", "inovacao.premiacao.pagamento"]


def _percent(part: Decimal, total: Decimal) -> str:
    return f"{(part * 100 / total).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%".replace(".", ",")


def approval_authority(facts: dict[str, CuratedFact], amount: float) -> RuleResult:
    require(facts, APPROVAL_KEYS)
    value = to_money(amount)
    nin = to_money(number(facts, "inovacao.alcada.gerente_nin"))
    dirtec = to_money(number(facts, "inovacao.alcada.diretor_dirtec"))
    if value <= nin:
        key, comparison = "inovacao.alcada.gerente_nin", f"{money(value)} ≤ {money(nin)}"
    elif value <= dirtec:
        key, comparison = "inovacao.alcada.diretor_dirtec", f"{money(nin)} < {money(value)} ≤ {money(dirtec)}"
    else:
        key, comparison = "inovacao.alcada.comite", f"{money(value)} > {money(dirtec)}"
    fact = facts[key]
    return RuleResult(
        rule="inovacao.alcada",
        steps=[
            step(
                facts,
                [key],
                label="Competência de aprovação do gasto de prototipagem por ideia",
                rule=fact.value_text,
                result_text=fact.responsible,
                result_value=float(value),
                computation=[comparison, f"Faixa {fact.value_text} → {fact.responsible}"],
            )
        ],
        assumptions=[
            "Aplica-se ao gasto de prototipagem por ideia; premiações e o orçamento total são aprovados pela DIRAF.",
            "A NG_012, norma das alçadas citada pelos documentos, não está no acervo.",
        ],
    )


def budget_breakdown(facts: dict[str, CuratedFact]) -> RuleResult:
    require(facts, BUDGET_KEYS)
    total = to_money(number(facts, "inovacao.orcamento.total"))
    declared_prizes = to_money(number(facts, "inovacao.orcamento.premiacoes"))
    items = {key: to_money(number(facts, key)) for key in BUDGET_ITEMS}
    warnings = []

    item_sum = sum(items.values(), Decimal("0.00"))
    steps = [
        step(
            facts,
            ["inovacao.orcamento.total", *BUDGET_ITEMS],
            label="Orçamento total da edição 2027",
            rule="Soma dos cinco itens do orçamento (NT_2026-021, item 3)",
            result_text=money(item_sum),
            result_value=float(item_sum),
            computation=[
                " + ".join(money(value) for value in items.values()) + f" = {money(item_sum)}",
                f"Total declarado: {money(total)}",
            ],
        )
    ]
    if item_sum != total:
        warnings.append(f"A soma dos itens ({money(item_sum)}) difere do total declarado ({money(total)}).")

    placement = sum((to_money(number(facts, key)) for key in PRIZES), Decimal("0.00"))
    budget_placement = items["inovacao.orcamento.premiacao_colocacao"]
    steps.append(
        step(
            facts,
            [*PRIZES, "inovacao.orcamento.premiacao_colocacao"],
            label="Premiação por colocação",
            rule="1º, 2º e 3º lugares do RG_1100 (item 4.5.1)",
            result_text=money(placement),
            result_value=float(placement),
            computation=[" + ".join(money(to_money(number(facts, key))) for key in PRIZES) + f" = {money(placement)}"],
        )
    )
    if placement != budget_placement:
        warnings.append(
            f"Prêmios por colocação ({money(placement)}) diferem do item orçado ({money(budget_placement)})."
        )

    arenas = days(facts, "inovacao.arenas.quantidade")
    arena_prize = to_money(number(facts, "inovacao.premio.arena"))
    arena_total = arena_prize * arenas
    budget_arena = items["inovacao.orcamento.premiacao_arena"]
    steps.append(
        step(
            facts,
            ["inovacao.arenas.quantidade", "inovacao.premio.arena", "inovacao.orcamento.premiacao_arena"],
            label="Premiação por arena",
            rule="Ideia melhor colocada de cada arena, cumulativa com a colocação (RG_1100, item 4.5.2)",
            result_text=money(arena_total),
            result_value=float(arena_total),
            computation=[f"{arenas} arenas × {money(arena_prize)} = {money(arena_total)}"],
        )
    )
    if arena_total != budget_arena:
        warnings.append(f"Prêmios por arena ({money(arena_total)}) diferem do item orçado ({money(budget_arena)}).")

    prizes = budget_placement + budget_arena
    steps.append(
        step(
            facts,
            [
                "inovacao.orcamento.premiacoes",
                "inovacao.orcamento.premiacao_colocacao",
                "inovacao.orcamento.premiacao_arena",
                "inovacao.orcamento.total",
            ],
            label="Premiações dentro do orçamento total",
            rule="Premiações (colocação + arena) são parte do orçamento total, não um orçamento à parte",
            result_text=money(prizes),
            result_value=float(prizes),
            computation=[
                f"{money(budget_placement)} + {money(budget_arena)} = {money(prizes)}",
                f"Declarado na NT_2026-021: {money(declared_prizes)}",
                f"{money(prizes)} ÷ {money(total)} = {_percent(prizes, total)} do orçamento total",
                f"Demais itens: {money(total)} − {money(prizes)} = {money(total - prizes)}",
            ],
        )
    )
    if prizes != declared_prizes:
        warnings.append(
            f"A soma das premiações ({money(prizes)}) difere do valor declarado ({money(declared_prizes)})."
        )

    for key, value in items.items():
        fact = facts[key]
        steps.append(
            step(
                facts,
                [key, "inovacao.orcamento.total"],
                label="Participação: " + fact.statement.removeprefix("Item do orçamento da edição 2027: ").rstrip("."),
                rule="Participação do item no orçamento total",
                result_text=_percent(value, total),
                result_value=float(value),
                computation=[f"{money(value)} ÷ {money(total)} = {_percent(value, total)}"],
            )
        )
    return RuleResult(
        rule="inovacao.orcamento",
        steps=steps,
        warnings=warnings,
        assumptions=["Percentuais arredondados para uma casa decimal, como na memória de cálculo da NT_2026-021."],
    )


def prize_payment_deadline(facts: dict[str, CuratedFact]) -> RuleResult:
    require(facts, PAYMENT_KEYS)
    award = facts["inovacao.edicao_2027.fase_7"].ends_on
    offset = days(facts, "inovacao.premiacao.pagamento")
    deadline = award + timedelta(days=offset)
    return RuleResult(
        rule="inovacao.pagamento_premiacao",
        steps=[
            step(
                facts,
                PAYMENT_KEYS,
                label="Pagamento das premiações em dinheiro",
                rule=facts["inovacao.premiacao.pagamento"].value_text,
                result_text=br_date(deadline),
                result_date=deadline,
                computation=[f"Premiação em {br_date(award)} + {offset} dias = {br_weekday(deadline)}"],
            )
        ],
        assumptions=["Prazo contado em dias corridos; a fonte não indica dias úteis.", "Pagamento somente em folha."],
    )
