"""Gera um acervo sintético mínimo para os roteiros de ponta a ponta na CI.

Uso: python tests/e2e/acervo_sintetico.py <pasta-de-saída>

O acervo de referência do desafio não é versionado. Este gera PDFs próprios, no formato de cabeçalho ACME
lido por backend/app/document_parser.py, com o mínimo que os roteiros conferem:
- Férias: NG_111 v3.0.0 (AC-01 no item 4.3.1, p. 2; aviso no 4.5.3, p. 3; estagiários no 4.12, p. 4)
  e PX_1111-001 v1.0.0 (precedência no 2.2, p. 1; aviso no 8.4.2, p. 3), como nos testes da #15 (AC-03);
- Inovação e Locação: uma norma cada, só para os temas existirem.
Os textos são resumos escritos para teste, não cópias do acervo. Os fatos curados ficam pendentes neste acervo.
"""

import sys
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

NG_111 = [
    """Documento: Norma Geral
Título: Férias
Sigla e Número: NG_111 Versão: 3.0.0
Fase: Vigente Vigência: 03/08/2026 a 03/02/2028
DOCUMENTO SINTÉTICO.
2.2. Esta norma substitui a NG_111 versão 2.0.0.""",
    """4.3. Solicitação de férias.
4.3.1. O empregado registra a solicitação de férias com antecedência mínima de 45 dias corridos
da data de início pretendida.""",
    """4.5.2. Decisão do gestor imediato: até 7 dias corridos depois do registro da solicitação.
4.5.3. Emissão do aviso pela GGC: até 35 dias antes.
4.5.4. Assinatura do aviso pelo empregado: até 5 dias úteis depois do recebimento.""",
    """4.12. Estagiários e aprendizes não são regidos por esta norma e seguem o termo de compromisso
ou o contrato de aprendizagem.""",
]
PX_1111_001 = [
    """Documento: Procedimento
Título: Procedimento de Férias
Sigla e Número: PX_1111-001 Versão: 1.0.0
Fase: Vigente Vigência: 10/08/2026 a 10/02/2028
Vinculado a: NG_111
DOCUMENTO SINTÉTICO.
2.2. O procedimento herda a numeração da NG_111 e a ela se subordina. Em
divergência, prevalece a NG_111.""",
    "8.3. Decidir.",
    """8.4. Emitir o aviso (até D-35).
8.4.1. Cabe à GGC conferir o saldo e as faltas conforme o TB_1111-001 e emitir o aviso a partir da fila.
8.4.2. Se a solicitação foi aprovada com menos de 35 dias para o início, a GGC
emite o aviso no dia seguinte à aprovação.""",
]


def norma(code, title, rule):
    return [
        f"""Documento: Norma Geral
Título: {title}
Sigla e Número: {code} Versão: 1.0.0
Fase: Vigente Vigência: 01/01/2026 a 31/12/2027
DOCUMENTO SINTÉTICO.
1.1. {rule}"""
    ]


ACERVO = {
    "ferias/NG_111.pdf": NG_111,
    "ferias/PX_1111-001.pdf": PX_1111_001,
    "inovacao/NG_901.pdf": norma("NG_901", "Inovação (teste)", "Cada ideia é avaliada pelo comitê em até 30 dias."),
    "locacao/NG_902.pdf": norma("NG_902", "Locação (teste)", "Cada contrato de locação tem um gestor designado."),
}


def make_pdf(pages):
    writer = PdfWriter()
    for value in pages:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
                NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        lines = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in value.split("\n")]
        stream = DecodedStreamObject()
        stream.set_data(
            ("BT /F1 12 Tf 14 TL 40 700 Td " + " T* ".join(f"({x}) Tj" for x in lines) + " ET").encode("cp1252")
        )
        page[NameObject("/Contents")] = writer._add_object(stream)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("uso: acervo_sintetico.py <pasta-de-saída>")
    root = Path(sys.argv[1])
    for relative, pages in ACERVO.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(make_pdf(pages))
    print(f"acervo sintético: {len(ACERVO)} PDFs em {root}")
