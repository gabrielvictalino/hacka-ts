from io import BytesIO
from uuid import uuid4

import pytest
from app.db import get_engine
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import text


def make_pdf(texts: list[str]) -> bytes:
    writer = PdfWriter()
    for value in texts:
        page = writer.add_blank_page(width=612, height=792)
        if value:
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
            stream = DecodedStreamObject()
            lines = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in value.split("\n")]
            operators = " T* ".join(f"({line}) Tj" for line in lines)
            stream.set_data(f"BT /F1 12 Tf 14 TL 40 700 Td {operators} ET".encode("cp1252"))
            page[NameObject("/Contents")] = writer._add_object(stream)
    result = BytesIO()
    writer.write(result)
    return result.getvalue()


@pytest.fixture
def topic():
    identifier = uuid4()
    with get_engine().begin() as connection:
        connection.execute(
            text("INSERT INTO topics(id, name) VALUES (:id, :name)"),
            {"id": identifier, "name": f"test-{identifier}"},
        )
    yield identifier
    with get_engine().begin() as connection:
        connection.execute(text("DELETE FROM document_versions WHERE topic_id=:id"), {"id": identifier})
        connection.execute(text("DELETE FROM documents WHERE topic_id=:id"), {"id": identifier})
        connection.execute(text("DELETE FROM topics WHERE id=:id"), {"id": identifier})
