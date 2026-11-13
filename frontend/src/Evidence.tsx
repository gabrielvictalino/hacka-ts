import { forwardRef } from "react";
import type { components } from "../../packages/contracts";

type Citation = components["schemas"]["Citation"];

export function citationLabel(c: Citation) {
  return `${c.code || c.title} · ${c.version || "versão não identificada"} · p. ${c.physical_page}${c.section ? ` · ${c.section}` : ""}`;
}

export const EvidencePanel = forwardRef<HTMLElement, { evidence: Citation; onClose: () => void; closeLabel: string }>(
  function EvidencePanel({ evidence, onClose, closeLabel }, ref) {
    return <aside ref={ref} tabIndex={-1} className="evidence document-reader" aria-label="Evidência selecionada">
      <div className="reader-back"><button className="link" onClick={onClose}>← {closeLabel}</button></div>
      <div className="reader-heading"><div><h2>{evidence.title}</h2><p>{evidence.code} · {evidence.version || "Versão não identificada"} · Página física {evidence.physical_page}</p></div>
        <div className="reader-original"><a className="button" href={`/api/documents/${evidence.version_id}/file#page=${evidence.physical_page}`} target="_blank" rel="noreferrer">Abrir PDF nesta página</a></div>
      </div>
      <div className="evidence-layout"><div className="reader-pages"><h2>Página citada</h2><div className="reader-thumbnail"><span>{evidence.excerpt}</span></div><p>Página {evidence.physical_page}</p></div>
        <div className="reader-center"><div className="reader-toolbar">Página {evidence.physical_page} · {evidence.section || "Item ou cláusula não identificado"}</div><div className="reader-sheet"><div className="reader-citation"><span>Trecho citado</span><blockquote>{evidence.excerpt}</blockquote></div><p className="reader-sheet-page">Página física {evidence.physical_page}</p></div></div>
        <div className="reader-source"><h2>Fonte e evidência</h2><p><strong>{evidence.code || evidence.title}</strong></p><p>{evidence.document_type} · {evidence.document_layer}</p><p>{evidence.declared_phase || "Fase não declarada"}</p><p>Vigência publicada: {evidence.valid_from || "início não identificado"} a {evidence.valid_until || "fim não identificado"}.</p><small>ID da versão: {evidence.version_id}</small><button onClick={onClose}>{closeLabel}</button></div>
      </div>
    </aside>;
  },
);
