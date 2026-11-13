"""Gera os PDFs do teste de interface com identificador único (evita reaproveitar duplicados)."""
from io import BytesIO
import os
import sys
from pathlib import Path
from uuid import uuid4

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

run = uuid4().hex[:8]
out = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("IPBOT_E2E_FILES", "."))
out.mkdir(parents=True, exist_ok=True)


def pdf(lines):
    w = PdfWriter()
    p = w.add_blank_page(width=612, height=792)
    w.add_metadata({"/Title": f"Teste de interface {run}"})
    if lines:
        f = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                              NameObject("/BaseFont"): NameObject("/Helvetica"),
                              NameObject("/Encoding"): NameObject("/WinAnsiEncoding")})
        p[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): w._add_object(f)})})
        s = DecodedStreamObject()
        s.set_data(("BT /F1 12 Tf 14 TL 40 700 Td " + " T* ".join(f"({x}) Tj" for x in lines) + " ET").encode("cp1252"))
        p[NameObject("/Contents")] = w._add_object(s)
    b = BytesIO()
    w.write(b)
    return b.getvalue()


open(out / "interface-valido.pdf", "wb").write(
    pdf([f"Documento de interface da issue 12 ({run}).", "4.2. O prazo de interface e de 11 dias corridos."]))
open(out / "interface-sem-texto.pdf", "wb").write(pdf([]))
print("PDFs gerados", run)
