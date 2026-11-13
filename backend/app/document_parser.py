"""Regras do cabeçalho ACME e recortes literais, sem extração de fatos."""

import re
from datetime import datetime

CODE = r"[A-Z]{2,5}_\d+(?:-\d+)?"
LABELS = (
    r"Documento|Título|Sigla e Número|Versão|Elaborado por|Aprovado por|Fase|"
    r"Vigência|Aprovado em|Assinada em|Vinculado a|Referência"
)
SECTION = re.compile(
    r"^[ \t]*(?P<section>\d+(?:\.\d+)*\.(?!\d)|\d+(?:\.\d+)+(?=\s)|"
    r"CLÁUSULA\s+(?:[A-ZÀ-Ú]+|\d+)|Anexo\s+[A-Z0-9]+|Tabela\s+\d+|Bloco\s+[A-Z])(?=\s|[—–:-])",
    re.MULTILINE | re.IGNORECASE,
)


def read_header(first_page: str) -> dict:
    header = first_page.split("DOCUMENTO SINTÉTICO", 1)[0]

    def field(label):
        match = re.search(
            rf"(?:^|\s)(?:{label}):\s*(.*?)(?=\s+(?:{LABELS}):|$)",
            header,
            re.DOTALL | re.IGNORECASE,
        )
        return " ".join(match[1].split()) if match else None

    code_match = re.search(CODE, field("Sigla e Número") or "")
    version_match = re.fullmatch(r"\d+\.\d+\.\d+", field("Versão") or "")
    validity = re.findall(r"\d{2}/\d{2}/\d{4}", field("Vigência") or "")
    try:
        dates = [datetime.strptime(value, "%d/%m/%Y").date() for value in validity]
    except ValueError:
        dates = []
    links = re.findall(CODE, " ".join(filter(None, [field("Vinculado a"), field("Referência")])))
    code = code_match[0] if code_match else None
    layer = {
        "NG": "norma geral",
        "PX": "procedimento vinculado",
        "FM": "apoio",
        "TB": "apoio",
        "FL": "apoio",
        "RG": "regulamento de programa",
        "CTR": "instrumento contratual",
        "NT": "fundamentação de decisão",
    }.get(code.split("_")[0] if code else "")
    return {
        "title": field("Título"),
        "code": code,
        "version": version_match[0] if version_match else None,
        "document_type": field("Documento"),
        "document_layer": layer,
        "declared_phase": field("Fase"),
        "valid_from": dates[0] if dates else None,
        "valid_until": dates[1] if len(dates) > 1 else None,
        "linked_codes": list(dict.fromkeys(links)),
    }


def page_passages(page: str, previous_section: str | None = None):
    """Uma passagem nunca cruza páginas nem divide um item por tamanho arbitrário."""
    matches = list(SECTION.finditer(page))
    start, section = 0, previous_section
    for match in matches:
        excerpt = page[start : match.start()].strip()
        if excerpt:
            yield section, excerpt
        start, section = match.start(), match["section"].rstrip(".")
    excerpt = page[start:].strip()
    if excerpt:
        yield section, excerpt
