"""Mudanças entre edições revisadas manualmente contra os PDFs do acervo.

Cada mudança compara duas edições do mesmo documento. Ela só é apresentada quando todos os trechos são
encontrados nas edições exatas publicadas. Uma mudança de versão não é divergência: a edição anterior deixa
de ser aplicável a partir do início da sucessora, mas continua consultável como fonte histórica.
"""

from dataclasses import dataclass

from app.fatos.catalogo import Source


@dataclass(frozen=True)
class CuratedChange:
    key: str
    code: str
    attribute: str
    summary: str
    from_version: str
    to_version: str
    before_text: str
    after_text: str
    before: tuple[Source, ...]
    after: tuple[Source, ...]
    note: str | None = None


CHANGES = (
    CuratedChange(
        key="ferias.ng111.antecedencia_solicitacao",
        code="NG_111",
        attribute="antecedencia_solicitacao",
        summary="Antecedência mínima da solicitação de férias",
        from_version="2.0.0",
        to_version="3.0.0",
        before_text="30 dias",
        after_text="45 dias corridos do início de gozo",
        before=(
            Source("NG_111", "2.0.0", 1, "2.3", "A solicitação deve ser feita com antecedência mínima de 30 dias."),
        ),
        after=(
            Source(
                "NG_111",
                "3.0.0",
                2,
                "4.3.1",
                "A solicitação é formal e feita no Portal Raiz (FM_1111-001) com antecedência mínima de 45 dias "
                "corridos do início de gozo.",
            ),
            Source("NG_111", "3.0.0", 1, "2.2", "Esta norma substitui a NG_111 versão 2.0.0."),
        ),
    ),
    CuratedChange(
        key="ferias.fm1111.antecedencia_solicitacao",
        code="FM_1111-001",
        attribute="antecedencia_solicitacao",
        summary="Antecedência informada no formulário de solicitação",
        from_version="1.0.0",
        to_version="2.0.0",
        before_text="30 dias",
        after_text="45 dias",
        before=(
            Source(
                "FM_1111-001",
                "1.0.0",
                1,
                "Instrução de envio",
                "Preencher e enviar ao gerente da unidade com antecedência mínima de 30 dias, conforme a NG_111.",
            ),
        ),
        after=(
            Source(
                "FM_1111-001",
                "2.0.0",
                2,
                "Bloco D",
                "Declaro ter ciência de que a solicitação exige 45 dias de antecedência.",
            ),
            Source(
                "FM_1111-001",
                "2.0.0",
                2,
                "Histórico de versões",
                "2.0.0 10/08/2026 Antecedência de 45 dias",
            ),
        ),
    ),
    CuratedChange(
        key="inovacao.rg1100.ideias_por_proponente",
        code="RG_1100",
        attribute="ideias_por_proponente",
        summary="Limite de ideias por proponente",
        from_version="1.0.0",
        to_version="2.0.0",
        before_text="Até 3 ideias",
        after_text="Até 2 ideias por edição",
        before=(),
        after=(
            Source("RG_1100", "2.0.0", 2, "4.1.2", "Cada proponente pode inscrever até 2 ideias por edição."),
            Source(
                "RG_1100",
                "2.0.0",
                1,
                "2.1",
                "1.0.0 02/03/2026 Primeira edição: até 3 ideias por proponente",
            ),
            Source("RG_1100", "2.0.0", 9, "Anexo K", "Ideias por proponente Até 3 Até 2"),
        ),
        note="O PDF da versão 1.0.0 não consta do acervo. O valor anterior vem do histórico da versão 2.0.0.",
    ),
)
