import { forwardRef } from "react";
import type { components } from "../../packages/contracts";

type Citation = components["schemas"]["Citation"];

export function citationLabel(c: Citation) {
  return `${c.code || c.title} · ${c.version || "versão não identificada"} · p. ${c.physical_page}${c.section ? ` · ${c.section}` : ""}`;
}

export const EvidencePanel = forwardRef<HTMLElement, { evidence: Citation; onClose: () => void; closeLabel: string }>(
  function EvidencePanel({ evidence, onClose, closeLabel }, ref) {
    return <aside ref={ref} tabIndex={-1} className="evidence" aria-label="Evidência selecionada">
      <h3>{evidence.title}</h3>
      <p>{evidence.code} · {evidence.version || "Versão não identificada"} · Página física {evidence.physical_page} · {evidence.section || "Item ou cláusula não identificado"}</p>
      <p>{evidence.document_type} · {evidence.document_layer} · {evidence.declared_phase || "Fase não declarada"}</p>
      <p>Vigência publicada: {evidence.valid_from || "início não identificado"} a {evidence.valid_until || "fim não identificado"}.</p>
      <blockquote>{evidence.excerpt}</blockquote>
      <p><a href={`/api/documents/${evidence.version_id}/file#page=${evidence.physical_page}`} target="_blank" rel="noreferrer">Abrir PDF nesta página</a></p>
      <small>ID da versão: {evidence.version_id}</small>
      <button onClick={onClose}>{closeLabel}</button>
    </aside>;
  },
);
