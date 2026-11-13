"""Roteiro ponta a ponta da #12 pelo proxy do Vite, com as mesmas chamadas do frontend.

Requer acervo sintético importado, fatos publicados e o SSO simulado (AUTH_DEMO_ENABLED=true).
Endereço: IPBOT_BASE_URL (padrão http://127.0.0.1:5173).
Não imprime cookies, tokens nem segredos. Saída: uma linha por verificação.
"""
import os
import sys
import time
from io import BytesIO

import httpx
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

BASE = os.environ.get("IPBOT_BASE_URL", "http://127.0.0.1:5173")
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'OK  ' if ok else 'FALHA'} {name}{(' · ' + detail) if detail else ''}")


def pdf(lines):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    if lines:
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica"),
                                 NameObject("/Encoding"): NameObject("/WinAnsiEncoding")})
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        ops = " T* ".join(f"({line}) Tj" for line in lines)
        stream.set_data(f"BT /F1 12 Tf 14 TL 40 700 Td {ops} ET".encode("cp1252"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def session_for(name_part):
    client = httpx.Client(base_url=BASE, timeout=30)
    users = client.get("/api/auth/demo/users").json()
    user = next(u for u in users if name_part in u["name"])
    token = client.post("/api/auth/demo/assertion", json={"user_id": user["subject"]}).json()["token"]
    callback = client.post("/auth/callback", json={"token": token})
    return client, callback


anon = httpx.Client(base_url=BASE, timeout=30)
check("Frontend servido pelo Vite", anon.get("/").status_code == 200)
check("Sem sessão, /eu responde 401", anon.get("/eu").status_code == 401)
check("Sem sessão, temas são negados", anon.get("/api/topics").status_code == 401)
users = anon.get("/api/auth/demo/users").json()
check("Simulador lista as três contas fictícias", len(users) == 3, ", ".join(u["name"] for u in users))

gestao, cb = session_for("Gestão")
me = gestao.get("/eu").json()
check("Gestão entra pelo callback do SSO simulado", cb.status_code == 200 and me["role"] == "gestao")
check("Gestão tem permissão de upload", "documents:ingest" in me["permissions"])
topics = {t["name"]: t["id"] for t in gestao.get("/api/topics").json()}
check("Temas do acervo importados", {"Férias", "Inovação", "Locação"} <= set(topics), ", ".join(sorted(topics)))
ferias = topics["Férias"]

for _ in range(60):
    versions = gestao.get("/api/documents", params={"topic_id": ferias}).json()
    if all(v["status"] in ("ready", "failed") for v in versions):
        break
    time.sleep(1)
# Só as versões do acervo têm código no cabeçalho; os PDFs de teste enviados antes ficam de fora da contagem.
acervo = [v for v in versions if v["code"]]
ready = [v for v in acervo if v["status"] == "ready"]
check("Versões do acervo de Férias processadas", len(ready) == len(acervo) == 7, f"{len(ready)}/{len(acervo)} prontas")
ng = next(v for v in versions if v["code"] == "NG_111" and v["version"] == "3.0.0")
check("Lista traz código, versão, tipo, fase e páginas", bool(ng["document_type"] and ng["declared_phase"] and ng["page_count"]),
      f"{ng['code']} v{ng['version']} · {ng['document_type']} · {ng['declared_phase']} · {ng['processed_pages']}/{ng['page_count']}")
curation = gestao.post("/api/fatos/curadoria")
check("Gestão publica fatos curados", curation.status_code == 200)

# Lote: PDF válido, PDF sem texto (falha no worker) e arquivo que não é PDF (rejeitado no envio).
valid = pdf(["Documento de teste da issue 12.", "4.1. O prazo de teste e de 9 dias corridos."])
blank = pdf([])
files = [("files", ("teste-12-valido.pdf", valid, "application/pdf")),
         ("files", ("teste-12-sem-texto.pdf", blank, "application/pdf")),
         ("files", ("nao-e-pdf.pdf", b"isto nao e um pdf", "application/pdf"))]
batch = gestao.post("/api/documents/batch", data={"topic_id": ferias}, files=files)
body = batch.json()
check("Lote devolve um resultado por arquivo, na ordem", batch.status_code == 202 and [b["filename"] for b in body]
      == ["teste-12-valido.pdf", "teste-12-sem-texto.pdf", "nao-e-pdf.pdf"])
check("Arquivo inválido volta com motivo legível", body[2]["result"] is None and bool(body[2]["error"]), body[2]["error"] or "")
again = gestao.post("/api/documents/batch", data={"topic_id": ferias},
                    files=[("files", ("teste-12-valido.pdf", valid, "application/pdf"))]).json()
check("Reenvio do mesmo PDF é marcado como duplicado", again[0]["result"]["duplicate"] is True)

new_ids = {body[0]["result"]["version_id"]: "valido", body[1]["result"]["version_id"]: "sem-texto"}
for _ in range(60):
    current = {v["id"]: v for v in gestao.get("/api/documents", params={"topic_id": ferias}).json()}
    if all(current[i]["status"] in ("ready", "failed") for i in new_ids):
        break
    time.sleep(1)
by_kind = {kind: current[i] for i, kind in new_ids.items()}
check("PDF válido do lote fica pronto para consulta", by_kind["valido"]["status"] == "ready")
failed = by_kind["sem-texto"]
check("PDF sem texto fica como falha com motivo", failed["status"] == "failed" and bool(failed["error"]), failed["error"] or "")
retry = gestao.post(f"/api/documents/{failed['id']}/retry")
check("Tentar novamente aceita o reenvio", retry.status_code == 202, f"status {retry.json().get('status')}")

empregado, _ = session_for("empregada")
me = empregado.get("/eu").json()
check("Empregado entra sem permissão de upload", me["role"] == "empregado" and "documents:ingest" not in me["permissions"])
denied = empregado.post("/api/documents/batch", data={"topic_id": ferias},
                        files=[("files", ("x.pdf", valid, "application/pdf"))])
check("Upload pelo empregado é negado (403)", denied.status_code == 403)
check("Retry pelo empregado é negado (403)", empregado.post(f"/api/documents/{failed['id']}/retry").status_code == 403)
check("Empregado pode listar documentos do tema", empregado.get("/api/documents", params={"topic_id": ferias}).status_code == 200)

answer = empregado.post("/perguntar", json={"topic_id": ferias, "reference_date": "2026-11-12",
                                            "question": "Com quantos dias de antecedência devo pedir férias?"}).json()
citations = [c for claim in answer["claims"] for c in claim["citations"]]
check("AC-01 responde com afirmação sustentada", answer["status"] in ("supported", "partial") and bool(citations),
      f"status {answer['status']} · modo {answer['mode']}")
first = citations[0] if citations else None
if first:
    check("Citação traz documento, versão, página física e trecho",
          bool(first["code"] and first["version"] and first["physical_page"] >= 1 and first["excerpt"]),
          f"{first['code']} v{first['version']} p. {first['physical_page']} {first['section'] or ''}")
    original = empregado.get(f"/api/documents/{first['version_id']}/file")
    check("Original da citação abre como PDF", original.status_code == 200
          and original.headers["content-type"].startswith("application/pdf"))
    resolved = empregado.get(f"/api/citations/{first['passage_id']}")
    check("Citação resolve a mesma evidência", resolved.status_code == 200 and resolved.json()["excerpt"] == first["excerpt"])

gap = empregado.post("/perguntar", json={"topic_id": ferias, "reference_date": "2026-11-12",
                                         "question": "Qual o valor do aluguel do coworking?"}).json()
check("Pergunta fora do tema não é completada", gap["status"] in ("insufficient", "partial"), f"status {gap['status']}")

print(f"\n{sum(results)}/{len(results)} verificações passaram")
sys.exit(0 if all(results) else 1)
