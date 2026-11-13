"""Divergências entre fontes cadastradas por curadoria manual contra os PDFs do acervo.

No MVP, o único caso apresentado é o cenário AC-03. A detecção automática de divergências em todo o acervo,
inclusive em PDFs inéditos, pertence à evolução do produto. Cada passagem aponta para a edição exata revisada:
uma edição nova não herda a divergência e precisa de nova curadoria. Uma divergência nunca escolhe uma das
orientações; ela mostra as passagens e a precedência que a própria fonte declara.
"""

from dataclasses import dataclass
from datetime import date

from app.fatos.catalogo import Source

CURATOR = "Equipe IPBOT · revisão manual"
REVIEWED_ON = date(2026, 11, 13)
CURATION_NOTE = (
    "Divergência cadastrada por curadoria manual para a demonstração. A detecção automática de divergências "
    "entre todos os documentos, inclusive em PDFs inéditos, pertence à evolução do produto."
)


@dataclass(frozen=True)
class Guidance:
    """Orientação de uma fonte para o cenário, resumida pela curadoria e sustentada pelo trecho literal."""

    role: str
    guidance: str
    source: Source


@dataclass(frozen=True)
class Precedence:
    prevailing_code: str
    statement: str
    source: Source


@dataclass(frozen=True)
class CuratedDivergence:
    key: str
    scenario_id: str
    subject: str
    question: str
    scenario: str
    conditions: tuple[str, ...]
    consequence: str
    notice: str
    guidances: tuple[Guidance, ...]
    precedence: Precedence | None = None
    # Termos que levam o aviso curto a uma pergunta que cita as edições envolvidas sem recuperar as passagens.
    terms: tuple[str, ...] = ()


DIVERGENCES = (
    CuratedDivergence(
        key="ferias.aviso.aprovacao_com_menos_de_35_dias",
        scenario_id="AC-03",
        subject="Emissão do aviso de férias após aprovação tardia",
        question="A solicitação foi aprovada 32 dias antes das férias. Quando a GGC emite o aviso?",
        scenario="Solicitação de férias aprovada com menos de 35 dias para o início de gozo, como na aprovação em D-32.",
        conditions=(
            "A solicitação foi aprovada com menos de 35 dias corridos para o início de gozo.",
            "A NG_111 v3.0.0 e o PX_1111-001 v1.0.0 são aplicáveis na data de referência.",
            "O PX_1111-001 é vinculado à NG_111 e declara a própria subordinação a ela.",
        ),
        consequence=(
            "Com aprovação em D-32, o prazo da norma (aviso até D-35) já terminou na data da aprovação, e o "
            "procedimento indica a emissão no dia seguinte (D-31). As duas orientações não podem ser cumpridas "
            "ao mesmo tempo."
        ),
        notice=(
            "A NG_111 e o PX_1111-001 orientam de forma diferente a emissão do aviso de férias quando a "
            "aprovação ocorre com menos de 35 dias para o início."
        ),
        guidances=(
            Guidance(
                role="Norma geral",
                guidance="A GGC emite o aviso até 35 dias antes do início de gozo (D-35).",
                source=Source("NG_111", "3.0.0", 3, "4.5.3", "Emissão do aviso pela GGC: até 35 dias antes."),
            ),
            Guidance(
                role="Procedimento vinculado",
                guidance="Se a aprovação ocorrer com menos de 35 dias para o início, a GGC emite o aviso no dia "
                "seguinte à aprovação.",
                source=Source(
                    "PX_1111-001",
                    "1.0.0",
                    3,
                    "8.4.2",
                    "Se a solicitação foi aprovada com menos de 35 dias para o início, a GGC emite o aviso no dia "
                    "seguinte à aprovação.",
                ),
            ),
        ),
        precedence=Precedence(
            prevailing_code="NG_111",
            statement="O próprio procedimento declara que, em divergência, prevalece a NG_111.",
            source=Source("PX_1111-001", "1.0.0", 1, "2.2", "Em divergência, prevalece a NG_111."),
        ),
        terms=("aviso", "avisos"),
    ),
)
