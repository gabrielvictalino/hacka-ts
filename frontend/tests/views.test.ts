// Regressões do "Ver para" (visão de estagiário ou aprendiz). Executar: npm test
import assert from "node:assert/strict";
import { test } from "node:test";
import { INTERN_VIEW, VIEWS, internPassages, mentionsInterns } from "../src/views.ts";

function citation(passage: string, excerpt: string) {
  return {
    document_id: "d", version_id: "v", passage_id: passage, title: "Férias", code: "NG_111", version: "3.0.0",
    physical_page: 4, section: "4.12", excerpt, document_type: null, document_layer: null, declared_phase: null,
    valid_from: null, valid_until: null,
  };
}

test("a visão de estagiário faz parte do seletor", () => {
  assert.ok((VIEWS as readonly string[]).includes(INTERN_VIEW));
});

test("reconhece menção literal a estagiários e aprendizes, com e sem acento", () => {
  assert.equal(mentionsInterns("4.12. Estagiários e aprendizes não são regidos por esta norma."), true);
  assert.equal(mentionsInterns("estagiarios"), true);
  assert.equal(mentionsInterns("O aprendiz segue o contrato."), true);
  assert.equal(mentionsInterns("4.3.1. A solicitação é formal."), false);
});

test("seleciona só trechos que citam estagiários, sem repetir a passagem", () => {
  const rule = citation("p-412", "4.12. Estagiários e aprendizes não são regidos por esta norma.");
  const other = citation("p-431", "4.3.1. A solicitação é formal.");
  const result = {
    calculation: null, notice: null, mode: "extractive", status: "partial", reference_date: "2026-11-13",
    claims: [{ text: rule.excerpt, citations: [rule, other] }], passages: [rule, other], gaps: [], divergences: [],
  };
  const passages = internPassages(result as Parameters<typeof internPassages>[0]);
  assert.deepEqual(passages.map(p => p.passage_id), ["p-412"]);
});

test("sem menção, não devolve trecho algum (não inventa regra)", () => {
  const result = {
    calculation: null, notice: null, mode: "extractive", status: "insufficient", reference_date: "2026-11-13",
    claims: [], passages: [citation("p-431", "4.3.1. A solicitação é formal.")], gaps: ["x"], divergences: [],
  };
  assert.deepEqual(internPassages(result as Parameters<typeof internPassages>[0]), []);
});
