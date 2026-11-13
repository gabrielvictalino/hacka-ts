"""Fatos de Férias e Inovação revisados manualmente contra os PDFs do acervo.

Cada fato aponta para documento, versão, página física e item de uma edição específica. O trecho
(`quote`) é copiado literalmente do texto extraído e só é publicado se for encontrado na passagem
correspondente. Uma nova edição de qualquer documento não herda estes fatos: ela precisa de nova revisão.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

CURATOR = "Equipe IPBOT · revisão manual"
REVIEWED_ON = date(2026, 11, 12)

FERIAS = "Férias"
INOVACAO = "Inovação"


@dataclass(frozen=True)
class Source:
    code: str
    version: str
    page: int
    item: str
    quote: str


@dataclass(frozen=True)
class CuratedFact:
    key: str
    topic: str
    category: str
    attribute: str
    area: str
    responsible: str
    statement: str
    value_text: str
    sources: tuple[Source, ...]
    value: Decimal | None = None
    unit: str | None = None
    conditions: str | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)


def _ng111(page: int, item: str, quote: str) -> Source:
    return Source("NG_111", "3.0.0", page, item, quote)


def _px1111(page: int, item: str, quote: str) -> Source:
    return Source("PX_1111-001", "1.0.0", page, item, quote)


def _tb1111(page: int, item: str, quote: str) -> Source:
    return Source("TB_1111-001", "1.0.0", page, item, quote)


def _nt021(page: int, item: str, quote: str) -> Source:
    return Source("NT_2026-021", "1.0.0", page, item, quote)


def _rg1100(page: int, item: str, quote: str) -> Source:
    return Source("RG_1100", "2.0.0", page, item, quote)


def _px1130(page: int, item: str, quote: str) -> Source:
    return Source("PX_1130-001", "1.0.0", page, item, quote)


FERIAS_PRAZOS = (
    CuratedFact(
        key="ferias.programacao.intencao",
        topic=FERIAS,
        category="deadline",
        attribute="programacao_intencao_de_gozo",
        area="Empregado",
        responsible="Empregado",
        statement="Registrar no Portal Raiz a intenção de gozo do ano seguinte.",
        value_text="Entre 1º e 31 de outubro de cada ano",
        conditions="A programação não substitui a solicitação formal do item 4.3.",
        sources=(
            _ng111(2, "4.2.1", "Entre 1º e 31 de outubro de cada ano, o empregado registra no Portal Raiz a"),
            _ng111(2, "4.2.4", "A programação não substitui a solicitação formal do item 4.3."),
        ),
    ),
    CuratedFact(
        key="ferias.programacao.consolidacao",
        topic=FERIAS,
        category="deadline",
        attribute="programacao_consolidacao_da_equipe",
        area="Gestor imediato",
        responsible="Gestor imediato",
        statement="Consolidar a programação de férias da equipe.",
        value_text="Até 30 de novembro",
        sources=(_ng111(2, "4.2.2", "O gestor imediato consolida a programação da equipe até 30 de novembro."),),
    ),
    CuratedFact(
        key="ferias.programacao.calendario",
        topic=FERIAS,
        category="deadline",
        attribute="programacao_calendario_institucional",
        area="GGC",
        responsible="Gerência de Gente e Cultura (GGC)",
        statement="Publicar o calendário institucional de férias.",
        value_text="Até 15 de dezembro",
        sources=(_ng111(2, "4.2.3", "A GGC publica o calendário institucional de férias até 15 de dezembro."),),
    ),
    CuratedFact(
        key="ferias.solicitacao.antecedencia",
        topic=FERIAS,
        category="deadline",
        attribute="solicitacao_antecedencia_minima",
        area="Empregado",
        responsible="Empregado",
        statement="Solicitar as férias formalmente no Portal Raiz (FM_1111-001).",
        value=Decimal(45),
        unit="dias corridos antes do início de gozo",
        value_text="Até D-45",
        conditions="Solicitação com menos de 45 dias só é aceita por decisão do diretor da área, registrada no Portal Raiz.",
        sources=(
            _ng111(2, "4.3.1", "com antecedência\nmínima de 45 dias corridos do início de gozo."),
            _ng111(3, "4.5.1", "Solicitação: até 45 dias antes."),
            _ng111(2, "4.3.3", "Solicitação com menos de 45 dias só é aceita por decisão do diretor da\nárea"),
        ),
        tags=("jornada",),
    ),
    CuratedFact(
        key="ferias.inicio.dia_vedado",
        topic=FERIAS,
        category="deadline",
        attribute="inicio_de_gozo_dia_vedado",
        area="Empregado",
        responsible="Empregado",
        statement="Escolher um início de gozo em dia útil fora dos dias vedados.",
        value=Decimal(2),
        unit="dias úteis que antecedem feriado ou descanso semanal remunerado",
        value_text="Não pode cair nos 2 dias úteis que antecedem feriado ou descanso semanal remunerado",
        conditions="Dia útil é o dia que não seja sábado, domingo ou feriado na sede da ACME.",
        sources=(
            _ng111(
                2,
                "4.3.2",
                "O início de gozo deve ocorrer em dia útil e não pode cair nos 2 dias úteis\n"
                "que antecedem feriado ou descanso semanal remunerado.",
            ),
            _ng111(2, "3.7", "Dia útil: dia que não seja sábado, domingo ou feriado na sede da ACME."),
        ),
    ),
    CuratedFact(
        key="ferias.decisao.gestor",
        topic=FERIAS,
        category="deadline",
        attribute="decisao_do_gestor_imediato",
        area="Gestor imediato",
        responsible="Gestor imediato",
        statement="Decidir a solicitação: aprovar, recusar com justificativa ou propor nova data.",
        value=Decimal(7),
        unit="dias corridos depois do registro da solicitação",
        value_text="Até 7 dias corridos depois do registro",
        conditions="A ausência de decisão em 7 dias não equivale a aprovação: a solicitação é escalada ao diretor da área.",
        sources=(
            _ng111(3, "4.5.2", "Decisão do gestor imediato: até 7 dias corridos depois do registro da\nsolicitação."),
            _ng111(3, "4.6.2", "A ausência de decisão em 7 dias não equivale a aprovação"),
        ),
        tags=("jornada",),
    ),
    CuratedFact(
        key="ferias.decisao.diretor",
        topic=FERIAS,
        category="deadline",
        attribute="decisao_do_diretor_escalonamento",
        area="Diretor da área",
        responsible="Diretor da área",
        statement="Decidir a solicitação escalada por falta de decisão do gestor.",
        value=Decimal(3),
        unit="dias úteis depois do escalonamento",
        value_text="Até 3 dias úteis",
        conditions="Aplica-se quando o gestor não decide em 7 dias corridos.",
        sources=(
            _ng111(3, "4.6.2", "a solicitação é\nescalada ao diretor da área, que decide em até 3 dias úteis."),
            _tb1111(1, "Tabela 2", "Diretor da área até 3 dias úteis após o\nescalonamento"),
        ),
    ),
    CuratedFact(
        key="ferias.aviso.emissao",
        topic=FERIAS,
        category="deadline",
        attribute="emissao_do_aviso",
        area="GGC",
        responsible="Gerência de Gente e Cultura (GGC)",
        statement="Emitir o aviso de férias.",
        value=Decimal(35),
        unit="dias corridos antes do início de gozo",
        value_text="Até D-35",
        sources=(
            _ng111(3, "4.5.3", "Emissão do aviso pela GGC: até 35 dias antes."),
            _tb1111(2, "Tabela 2", "Emissão do aviso GGC até D-35"),
        ),
        tags=("jornada",),
    ),
    CuratedFact(
        key="ferias.aviso.assinatura_recebimento",
        topic=FERIAS,
        category="deadline",
        attribute="assinatura_do_aviso_apos_recebimento",
        area="Empregado",
        responsible="Empregado",
        statement="Assinar o aviso de férias depois de recebê-lo.",
        value=Decimal(5),
        unit="dias úteis depois do recebimento",
        value_text="Até 5 dias úteis depois do recebimento",
        conditions="Nunca depois de 30 dias antes do início de gozo.",
        sources=(
            _ng111(
                3,
                "4.5.4",
                "Assinatura do aviso pelo empregado: até 5 dias úteis depois do\n"
                "recebimento e nunca depois de 30 dias antes do início de gozo.",
            ),
        ),
        tags=("jornada",),
    ),
    CuratedFact(
        key="ferias.aviso.assinatura_limite",
        topic=FERIAS,
        category="deadline",
        attribute="assinatura_do_aviso_limite",
        area="Empregado",
        responsible="Empregado",
        statement="Data-limite absoluta para assinar o aviso de férias.",
        value=Decimal(30),
        unit="dias corridos antes do início de gozo",
        value_text="Nunca depois de D-30",
        conditions="Sem assinatura em D-30, a GGC notifica o gestor e o diretor; as férias não podem ser iniciadas sem aviso assinado.",
        sources=(
            _ng111(3, "4.5.4", "nunca depois de 30 dias antes do início de gozo."),
            _px1111(
                3,
                "8.5.2",
                "Sem assinatura em D-30, a GGC notifica o gestor e o diretor, e as férias não\n"
                "podem ser iniciadas sem aviso assinado.",
            ),
        ),
    ),
    CuratedFact(
        key="ferias.pagamento.antecedencia",
        topic=FERIAS,
        category="deadline",
        attribute="pagamento_das_ferias",
        area="GFI",
        responsible="Gerência de Finanças (GFI)",
        statement="Pagar as férias.",
        value=Decimal(3),
        unit="dias corridos antes do início de gozo",
        value_text="Até D-3",
        conditions="Se esse dia for sábado, domingo ou feriado, o pagamento é antecipado para o dia útil anterior.",
        sources=(
            _ng111(
                3,
                "4.5.5",
                "Pagamento: até 3 dias corridos antes; se esse dia for sábado, domingo ou\n"
                "feriado, o pagamento é antecipado para o dia útil anterior.",
            ),
        ),
        tags=("jornada",),
    ),
    CuratedFact(
        key="ferias.pagamento.ordem",
        topic=FERIAS,
        category="deadline",
        attribute="ordem_de_pagamento",
        area="GGC",
        responsible="Gerência de Gente e Cultura (GGC)",
        statement="Enviar a ordem de pagamento à GFI.",
        value=Decimal(5),
        unit="dias úteis após a assinatura do aviso",
        value_text="Até 5 dias úteis após a assinatura",
        sources=(
            _px1111(3, "8.6.1", "Cabe à GGC enviar a ordem de pagamento à GFI em até 5 dias úteis após a\nassinatura."),
        ),
    ),
    CuratedFact(
        key="ferias.alteracao.iniciativa_empregado",
        topic=FERIAS,
        category="deadline",
        attribute="alteracao_por_iniciativa_do_empregado",
        area="Empregado",
        responsible="Empregado, com anuência do gestor",
        statement="Alterar ou cancelar as férias por iniciativa do empregado.",
        value=Decimal(20),
        unit="dias corridos antes do início de gozo",
        value_text="Até D-20",
        conditions="Com anuência do gestor e uma única vez por período.",
        sources=(
            _ng111(
                4,
                "4.9.1",
                "Por iniciativa do empregado, com anuência do gestor, a alteração ou o\n"
                "cancelamento pode ser feito até 20 dias antes do início de gozo, uma única vez\n"
                "por período.",
            ),
        ),
    ),
    CuratedFact(
        key="ferias.alteracao.necessidade_servico",
        topic=FERIAS,
        category="deadline",
        attribute="alteracao_por_necessidade_de_servico",
        area="Diretor da área",
        responsible="Diretor da área",
        statement="Alterar as férias nos 20 dias que antecedem o início, apenas por necessidade de serviço.",
        value=Decimal(19),
        unit="dias corridos antes do início de gozo (a partir de)",
        value_text="De D-19 em diante",
        conditions="Somente por necessidade de serviço e por decisão do diretor da área.",
        sources=(
            _ng111(
                4,
                "4.9.2",
                "Nos 20 dias que antecedem o início, a alteração ocorre apenas por\n"
                "necessidade de serviço, por decisão do diretor da área.",
            ),
            _px1111(3, "8.7.2", "De D-19 em diante, só o diretor da área pode alterar, por necessidade de\nserviço."),
        ),
    ),
    CuratedFact(
        key="ferias.ressarcimento.comprovantes",
        topic=FERIAS,
        category="deadline",
        attribute="ressarcimento_envio_de_comprovantes",
        area="Empregado",
        responsible="Empregado",
        statement="Anexar os comprovantes para ressarcimento após alteração por necessidade de serviço.",
        value=Decimal(15),
        unit="dias corridos da alteração",
        value_text="Até 15 dias corridos da alteração",
        sources=(
            _px1111(
                3, "8.7.3", "Para ressarcimento, o empregado anexa comprovantes em até 15 dias\ncorridos da alteração"
            ),
        ),
    ),
    CuratedFact(
        key="ferias.abono.pedido",
        topic=FERIAS,
        category="deadline",
        attribute="abono_pecuniario_pedido",
        area="Empregado",
        responsible="Empregado",
        statement="Pedir o abono pecuniário na mesma solicitação de férias.",
        value=Decimal(15),
        unit="dias antes do término do período aquisitivo",
        value_text="Nunca depois de 15 dias antes do término do período aquisitivo",
        sources=(
            _ng111(
                3,
                "4.7.2",
                "O pedido é feito na mesma solicitação de férias e nunca depois de 15 dias\n"
                "antes do término do período aquisitivo.",
            ),
        ),
    ),
    CuratedFact(
        key="ferias.adiantamento_13.pedido",
        topic=FERIAS,
        category="deadline",
        attribute="adiantamento_13_pedido",
        area="Empregado",
        responsible="Empregado",
        statement="Pedir o adiantamento da 1ª parcela do 13º salário no Portal Raiz.",
        value_text="Entre 1º e 31 de janeiro",
        conditions="A parcela é paga junto com as férias do primeiro período do ano.",
        sources=(
            _ng111(3, "4.8.1", "O empregado pode pedir o adiantamento entre 1º e 31 de janeiro, no Portal\nRaiz."),
            _ng111(3, "4.8.2", "A parcela é paga junto com as férias do primeiro período do ano."),
        ),
    ),
    CuratedFact(
        key="ferias.vencimento.alerta",
        topic=FERIAS,
        category="deadline",
        attribute="alerta_de_ferias_a_vencer",
        area="GGC",
        responsible="Gerência de Gente e Cultura (GGC)",
        statement="Alertar o gestor sobre férias a vencer.",
        value=Decimal(120),
        unit="dias antes do fim do período concessivo",
        value_text="120 dias antes do fim do período concessivo",
        sources=(_ng111(4, "4.10.1", "A GGC alerta o gestor 120 dias antes do fim do período concessivo."),),
    ),
    CuratedFact(
        key="ferias.vencimento.programacao",
        topic=FERIAS,
        category="deadline",
        attribute="programacao_de_ferias_a_vencer",
        area="Gestor imediato",
        responsible="Gestor imediato",
        statement="Programar o gozo das férias a vencer.",
        value=Decimal(90),
        unit="dias antes do fim do período concessivo",
        value_text="Até 90 dias antes do fim do período concessivo",
        conditions="Sem programação nesse prazo, a GGC escala o caso à DIRAF.",
        sources=(
            _ng111(4, "4.10.2", "O gestor programa o gozo até 90 dias antes do fim do período concessivo."),
            _ng111(4, "4.10.3", "Sem programação nesse prazo, a GGC escala o caso à DIRAF."),
        ),
    ),
)

FERIAS_VALORES = (
    CuratedFact(
        key="ferias.direito.dias",
        topic=FERIAS,
        category="value",
        attribute="dias_de_ferias_por_periodo_aquisitivo",
        area="Empregado",
        responsible="Empregado",
        statement="Dias de férias gerados por 12 meses de período aquisitivo.",
        value=Decimal(30),
        unit="dias corridos",
        value_text="30 dias corridos",
        conditions="Reduzidos conforme as faltas injustificadas da tabela do TB_1111-001.",
        sources=(
            _ng111(
                2,
                "4.1.1",
                "Cada 12 meses de período aquisitivo geram 30 dias corridos de férias,\n"
                "reduzidos conforme as faltas injustificadas da tabela do TB_1111-001.",
            ),
        ),
    ),
    *(
        CuratedFact(
            key=f"ferias.faltas.faixa_{index}",
            topic=FERIAS,
            category="value",
            attribute="dias_de_ferias_por_faltas_injustificadas",
            area="GGC",
            responsible="Gerência de Gente e Cultura (GGC)",
            statement=f"Faltas injustificadas no período aquisitivo: {label}.",
            value=Decimal(days) if days is not None else None,
            unit="dias corridos de férias" if days is not None else None,
            value_text=text,
            conditions=f"Faixa de {label} faltas injustificadas no período aquisitivo.",
            sources=(_tb1111(1, "Tabela 1", quote),),
        )
        for index, (label, days, text, quote) in enumerate(
            (
                ("0 a 5", 30, "30 dias corridos", "0 a 5 30"),
                ("6 a 14", 24, "24 dias corridos", "6 a 14 24"),
                ("15 a 23", 18, "18 dias corridos", "15 a 23 18"),
                ("24 a 32", 12, "12 dias corridos", "24 a 32 12"),
                ("mais de 32", None, "Perda do direito no período", "Mais de 32 Perda do direito no período"),
            ),
            start=1,
        )
    ),
    CuratedFact(
        key="ferias.fracionamento.periodos",
        topic=FERIAS,
        category="value",
        attribute="fracionamento_limite_de_periodos",
        area="Empregado",
        responsible="Empregado",
        statement="Número máximo de períodos em que as férias podem ser divididas.",
        value=Decimal(3),
        unit="períodos",
        value_text="Até 3 períodos",
        conditions="Um dos períodos deve ter no mínimo 14 dias corridos; os demais, no mínimo 5 dias corridos cada.",
        sources=(
            _ng111(2, "4.4.1", "As férias podem ser divididas em até 3 períodos."),
            _ng111(
                2,
                "4.4.2",
                "Um dos períodos deve ter no mínimo 14 dias corridos; os demais, no mínimo\n5 dias corridos cada.",
            ),
        ),
    ),
    CuratedFact(
        key="ferias.abono.limite",
        topic=FERIAS,
        category="value",
        attribute="abono_pecuniario_limite",
        area="Empregado",
        responsible="Empregado",
        statement="Dias de férias que podem ser convertidos em abono pecuniário.",
        value=Decimal(10),
        unit="dias",
        value_text="Até 10 dias",
        conditions="O abono é pago junto com as férias.",
        sources=(
            _ng111(3, "4.7.1", "O empregado pode converter até 10 dias em abono."),
            _ng111(3, "4.7.3", "O abono é pago junto com as férias."),
        ),
    ),
    CuratedFact(
        key="ferias.ausencia.percentual",
        topic=FERIAS,
        category="value",
        attribute="limite_de_ausencia_simultanea",
        area="Gestor imediato",
        responsible="Gestor imediato",
        statement="Parcela máxima da equipe de férias ao mesmo tempo.",
        value=Decimal(30),
        unit="% da equipe, arredondado para baixo",
        value_text="No máximo 30% da equipe",
        conditions="Arredonda-se para baixo; em equipes de até 3 empregados, uma pessoa por vez (mínimo 1).",
        sources=(
            _ng111(
                3,
                "4.6.3",
                "No máximo 30% da equipe pode estar de férias ao mesmo tempo,\n"
                "arredondando-se para baixo; em equipes de até 3 empregados, uma pessoa por\nvez.",
            ),
            _tb1111(2, "Tabela 4", "(Regra: 30% da equipe, arredondado para baixo, mínimo 1.)"),
        ),
    ),
    CuratedFact(
        key="ferias.ressarcimento.limite",
        topic=FERIAS,
        category="value",
        attribute="ressarcimento_alteracao_por_necessidade_de_servico",
        area="GFI",
        responsible="GGC analisa; GFI paga na folha seguinte",
        statement="Ressarcimento de despesas comprovadas e não reembolsáveis na alteração por necessidade de serviço.",
        value=Decimal("2500.00"),
        unit="R$ por evento",
        value_text="Até R$ 2.500,00 por evento",
        conditions="Somente na alteração por necessidade de serviço e para despesas comprovadas e não reembolsáveis.",
        sources=(
            _ng111(
                4,
                "4.9.3",
                "Na alteração por necessidade de serviço, a ACME ressarce as despesas\n"
                "comprovadas e não reembolsáveis do empregado, até R$ 2.500,00 por evento.",
            ),
            _px1111(3, "8.7.3", "a GGC analisa e a GFI paga na folha seguinte, até R$\n2.500,00 por evento."),
        ),
    ),
)

_RG_PHASES = (
    (1, "Inscrição", date(2027, 2, 1), date(2027, 2, 28), "1 Inscrição 01/02/2027 a 28/02/2027", "Proponente"),
    (2, "Triagem de elegibilidade", None, date(2027, 3, 12), "2 Triagem de elegibilidade até 12/03/2027", "NIN"),
    (3, "Votação interna", date(2027, 3, 15), date(2027, 3, 26), "3 Votação interna 15/03/2027 a 26/03/2027", "NIN"),
    (4, "Imersão", date(2027, 4, 5), date(2027, 4, 9), "4 Imersão 05/04/2027 a 09/04/2027", "NIN"),
    (5, "Prototipagem", date(2027, 4, 12), date(2027, 5, 31), "5 Prototipagem 12/04/2027 a 31/05/2027", "Proponente"),
    (6, "Banca final", date(2027, 6, 15), date(2027, 6, 15), "6 Banca final 15/06/2027", "Banca final"),
    (7, "Premiação", date(2027, 6, 30), date(2027, 6, 30), "7 Premiação 30/06/2027", "DIRAF"),
)


def _phase_text(start: date | None, end: date) -> str:
    if start is None:
        return f"Até {end:%d/%m/%Y}"
    if start == end:
        return f"{end:%d/%m/%Y}"
    return f"{start:%d/%m/%Y} a {end:%d/%m/%Y}"


INOVACAO_PRAZOS = (
    *(
        CuratedFact(
            key=f"inovacao.edicao_2027.fase_{number}",
            topic=INOVACAO,
            category="deadline",
            attribute="calendario_da_edicao_2027",
            area=area,
            responsible=area,
            statement=f"Fase {number} do Programa Ideias em Campo 2027: {name}.",
            value=Decimal(number),
            unit="fase da edição 2027",
            value_text=_phase_text(start, end),
            starts_on=start,
            ends_on=end,
            conditions="Calendário da edição 2027 (RG_1100 v2.0.0); o funil corporativo do PX_1130-001 é outro processo.",
            sources=(_rg1100(2, "4.2", quote),),
            tags=("linha_do_tempo",),
        )
        for number, name, start, end, quote, area in _RG_PHASES
    ),
    CuratedFact(
        key="inovacao.elegibilidade.tempo_de_casa",
        topic=INOVACAO,
        category="deadline",
        attribute="elegibilidade_tempo_minimo_de_casa",
        area="Proponente",
        responsible="Proponente",
        statement="Tempo mínimo de casa para participar, contado na abertura das inscrições.",
        value=Decimal(6),
        unit="meses de casa em 01/02/2027",
        value_text="Mínimo de 6 meses de casa na abertura das inscrições (01/02/2027)",
        conditions="A NT não trata de empregados em afastamento na data da inscrição; o caso deve ser consultado ao NIN.",
        sources=(
            _nt021(2, "5.1", "Mínimo de 6 meses de casa na abertura das inscrições (01/02/2027)."),
            _nt021(
                2,
                "5.4",
                "A NT não trata de empregados em afastamento na data da inscrição; o\ncaso deve ser consultado ao NIN.",
            ),
        ),
    ),
    CuratedFact(
        key="inovacao.premiacao.pagamento",
        topic=INOVACAO,
        category="deadline",
        attribute="pagamento_das_premiacoes",
        area="DIRAF",
        responsible="DIRAF",
        statement="Pagar as premiações em dinheiro em folha.",
        value=Decimal(30),
        unit="dias após a premiação",
        value_text="Em até 30 dias após a premiação",
        conditions="Não há pagamento de prêmio fora da folha.",
        sources=(
            _rg1100(3, "4.5.4", "Prêmios em dinheiro são pagos em folha em até 30 dias após a premiação."),
            _nt021(2, "6.2", "Não há pagamento de prêmio fora da folha."),
        ),
    ),
    *(
        CuratedFact(
            key=f"inovacao.funil.{key}",
            topic=INOVACAO,
            category="deadline",
            attribute=f"funil_{key}",
            area=area,
            responsible=responsible,
            statement=statement,
            value=Decimal(days),
            unit=unit,
            value_text=value_text,
            conditions="Etapa do funil corporativo de inovação (PX_1130-001), distinto do calendário do programa.",
            sources=(_px1130(page, item, quote),),
        )
        for key, area, responsible, statement, days, unit, value_text, page, item, quote in (
            (
                "triagem",
                "NIN",
                "Núcleo de Inovação (NIN)",
                "Fazer a triagem das ideias protocoladas.",
                10,
                "dias úteis do protocolo",
                "Até 10 dias úteis do protocolo",
                2,
                "8.1.1",
                "Cabe ao NIN fazer a triagem em até 10 dias úteis do protocolo.",
            ),
            (
                "devolucao",
                "NIN",
                "Núcleo de Inovação (NIN)",
                "Devolver ao proponente as ideias incompletas, com orientação.",
                5,
                "dias úteis da triagem",
                "Até 5 dias úteis da triagem",
                2,
                "8.1.2",
                "em até 5 dias úteis da triagem.",
            ),
            (
                "pesquisa",
                "NIN",
                "NIN e proponente",
                "Pesquisar soluções existentes, internas e de mercado.",
                30,
                "dias corridos da priorização",
                "Até 30 dias corridos da priorização",
                2,
                "8.2.1",
                "mercado, em até 30 dias corridos da priorização.",
            ),
            (
                "prototipo",
                "NIN",
                "Proponente e NIN",
                "Construir o protótipo, com TRL mínimo 4 ao final.",
                60,
                "dias corridos",
                "Até 60 dias corridos",
                2,
                "8.3.1",
                "Cabe ao proponente e ao NIN construir o protótipo em até 60 dias corridos,\ncom TRL mínimo 4 ao final.",
            ),
            (
                "mvp",
                "DIRTEC",
                "DIRTEC aprova; NIN e proponente entregam",
                "Entregar o MVP aprovado pela DIRTEC.",
                120,
                "dias corridos da aprovação",
                "Até 120 dias corridos da aprovação",
                3,
                "8.4.3",
                "O MVP é entregue em até 120 dias corridos da aprovação",
            ),
            (
                "validacao",
                "NIN",
                "Núcleo de Inovação (NIN)",
                "Validar o MVP com usuários reais.",
                30,
                "dias corridos da entrega",
                "Até 30 dias corridos da entrega",
                3,
                "8.5.1",
                "Cabe ao NIN validar o MVP com usuários reais em até 30 dias corridos da\nentrega.",
            ),
        )
    ),
)

_BUDGET_CONDITIONS = "Parte do orçamento total de R$ 96.000,00 da edição 2027 (NT_2026-021)."

INOVACAO_VALORES = (
    CuratedFact(
        key="inovacao.orcamento.total",
        topic=INOVACAO,
        category="value",
        attribute="orcamento_total_da_edicao_2027",
        area="DIRAF",
        responsible="DIRAF",
        statement="Orçamento total do Programa Ideias em Campo 2027.",
        value=Decimal("96000.00"),
        unit="R$",
        value_text="R$ 96.000,00",
        conditions=(
            "Total do programa, dividido em cinco itens; não se confunde com os R$ 24.000,00 de premiações. "
            "Fica abaixo do limite do Comitê de Alçadas e é aprovado pela DIRAF (aprovação em 16/10/2026)."
        ),
        sources=(
            _nt021(1, "3", "Total 96.000,00"),
            _nt021(
                2,
                "4.5",
                "O orçamento total do programa (R$ 96.000,00) fica abaixo do limite do Comitê de\n"
                "Alçadas e é aprovado pela DIRAF.",
            ),
            _nt021(2, "7", "Aprovação: DIRAF, em 16/10/2026."),
        ),
        tags=("grafico_orcamento",),
    ),
    CuratedFact(
        key="inovacao.orcamento.premiacoes",
        topic=INOVACAO,
        category="value",
        attribute="orcamento_premiacoes_da_edicao_2027",
        area="DIRAF",
        responsible="DIRAF",
        statement="Verba de premiações (colocação e arena) da edição 2027.",
        value=Decimal("24000.00"),
        unit="R$",
        value_text="R$ 24.000,00",
        conditions=(
            "Subconjunto do orçamento total de R$ 96.000,00 (um quarto). Premiações por colocação e por arena são "
            "cumulativas e aprovadas pela DIRAF após a banca final; não se enquadram nas faixas de alçada."
        ),
        sources=(
            _nt021(2, "Anexo A", "a premiação por colocação e por arena soma R$ 24.000,00, um quarto do\norçamento;"),
            _nt021(2, "4.1", "Premiações: aprovadas pela DIRAF, após a banca final."),
        ),
        tags=("grafico_orcamento",),
    ),
    *(
        CuratedFact(
            key=f"inovacao.orcamento.{key}",
            topic=INOVACAO,
            category="value",
            attribute=f"orcamento_item_{key}",
            area="DIRAF",
            responsible="DIRAF",
            statement=f"Item do orçamento da edição 2027: {label}.",
            value=Decimal(amount),
            unit="R$",
            value_text=f"R$ {text}",
            conditions=extra or _BUDGET_CONDITIONS,
            sources=(_nt021(1, "3", quote),),
            tags=("grafico_orcamento", "item_orcamento"),
        )
        for key, label, amount, text, quote, extra in (
            (
                "premiacao_colocacao",
                "premiação por colocação",
                "16000.00",
                "16.000,00",
                "Premiação por colocação (8.000 + 5.000 + 3.000) 16.000,00",
                _BUDGET_CONDITIONS + " Integra os R$ 24.000,00 de premiações.",
            ),
            (
                "premiacao_arena",
                "premiação por arena",
                "8000.00",
                "8.000,00",
                "Premiação por arena (4 × 2.000) 8.000,00",
                _BUDGET_CONDITIONS + " Integra os R$ 24.000,00 de premiações.",
            ),
            ("imersao", "imersão", "30000.00", "30.000,00", "Imersão 30.000,00", None),
            (
                "kits_prototipagem",
                "kits de prototipagem",
                "36000.00",
                "36.000,00",
                "Kits de prototipagem 36.000,00",
                None,
            ),
            ("comunicacao", "comunicação", "6000.00", "6.000,00", "Comunicação 6.000,00", None),
        )
    ),
    *(
        CuratedFact(
            key=f"inovacao.premio.{key}",
            topic=INOVACAO,
            category="value",
            attribute=f"premio_{key}",
            area="DIRAF",
            responsible="DIRAF aprova e paga",
            statement=statement,
            value=Decimal(amount),
            unit="R$",
            value_text=f"R$ {text}",
            conditions=conditions,
            sources=(_rg1100(3, item, quote),),
        )
        for key, statement, amount, text, item, quote, conditions in (
            (
                "1_lugar",
                "Prêmio do 1º lugar por colocação.",
                "8000.00",
                "8.000,00",
                "4.5.1",
                "1º lugar R$ 8.000,00",
                "Premiação por colocação; cumulativa com a premiação por arena.",
            ),
            (
                "2_lugar",
                "Prêmio do 2º lugar por colocação.",
                "5000.00",
                "5.000,00",
                "4.5.1",
                "2º lugar R$ 5.000,00",
                "Premiação por colocação; cumulativa com a premiação por arena.",
            ),
            (
                "3_lugar",
                "Prêmio do 3º lugar por colocação.",
                "3000.00",
                "3.000,00",
                "4.5.1",
                "3º lugar R$\n3.000,00",
                "Premiação por colocação; cumulativa com a premiação por arena.",
            ),
            (
                "arena",
                "Prêmio da ideia melhor colocada de cada uma das quatro arenas.",
                "2000.00",
                "2.000,00",
                "4.5.2",
                "Por arena: a ideia melhor colocada de cada arena recebe R$ 2.000,00,\n"
                "cumulativos com a premiação por colocação.",
                "Por arena; cumulativo com a premiação por colocação.",
            ),
        )
    ),
    CuratedFact(
        key="inovacao.arenas.quantidade",
        topic=INOVACAO,
        category="value",
        attribute="quantidade_de_arenas",
        area="NIN",
        responsible="Núcleo de Inovação (NIN)",
        statement="Arenas temáticas do programa; cada uma premia sua ideia melhor colocada.",
        value=Decimal(4),
        unit="arenas",
        value_text="Quatro: Operação de Campo, Tecnologia, Pessoas e Sustentabilidade",
        sources=(
            _rg1100(1, "3.1", "Há quatro: Operação de Campo, Tecnologia,\nPessoas e Sustentabilidade."),
            _nt021(1, "3", "Premiação por arena (4 × 2.000) 8.000,00"),
        ),
    ),
    CuratedFact(
        key="inovacao.alcada.gerente_nin",
        topic=INOVACAO,
        category="value",
        attribute="alcada_gasto_de_prototipagem",
        area="NIN",
        responsible="Gerente do NIN",
        statement="Alçada do gerente do NIN para gasto de prototipagem por ideia.",
        value=Decimal("18000.00"),
        unit="R$ por ideia (limite superior)",
        value_text="Até R$ 18.000,00",
        conditions=(
            "Gasto de prototipagem por ideia. A premiação não se enquadra nessas faixas. "
            "A NG_012, norma das alçadas, não está no acervo."
        ),
        sources=(
            _nt021(2, "4.2", "Gasto de prototipagem por ideia até R$ 18.000,00: gerente do NIN."),
            _nt021(4, "Anexo C", "A premiação não se enquadra nessas faixas."),
        ),
        tags=("alcada",),
    ),
    CuratedFact(
        key="inovacao.alcada.diretor_dirtec",
        topic=INOVACAO,
        category="value",
        attribute="alcada_gasto_de_prototipagem",
        area="DIRTEC",
        responsible="Diretor da DIRTEC",
        statement="Alçada do diretor da DIRTEC para gasto de prototipagem por ideia.",
        value=Decimal("120000.00"),
        unit="R$ por ideia (limite superior)",
        value_text="De R$ 18.000,01 a R$ 120.000,00",
        conditions=(
            "Gasto de prototipagem por ideia, a partir de R$ 18.000,01. A premiação não se enquadra nessas faixas. "
            "A NG_012, norma das alçadas, não está no acervo."
        ),
        sources=(
            _nt021(2, "4.3", "Gasto entre R$ 18.000,01 e R$ 120.000,00: diretor da DIRTEC."),
            _nt021(4, "Anexo C", "A premiação não se enquadra nessas faixas."),
        ),
        tags=("alcada",),
    ),
    CuratedFact(
        key="inovacao.alcada.comite",
        topic=INOVACAO,
        category="value",
        attribute="alcada_gasto_de_prototipagem",
        area="Comitê de Alçadas",
        responsible="Comitê de Alçadas",
        statement="Gastos de prototipagem por ideia acima do limite da DIRTEC.",
        value=Decimal("120000.00"),
        unit="R$ por ideia (acima de)",
        value_text="Acima de R$ 120.000,00",
        conditions="A premiação não se enquadra nessas faixas. A NG_012, norma das alçadas, não está no acervo.",
        sources=(
            _nt021(2, "4.4", "Acima de R$ 120.000,00: Comitê de Alçadas."),
            _nt021(4, "Anexo C", "A premiação não se enquadra nessas faixas."),
        ),
        tags=("alcada",),
    ),
)

CATALOG: tuple[CuratedFact, ...] = FERIAS_PRAZOS + FERIAS_VALORES + INOVACAO_PRAZOS + INOVACAO_VALORES
