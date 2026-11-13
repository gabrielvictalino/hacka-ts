import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { components } from "../../packages/contracts";
import { EvidencePanel, citationLabel } from "./Evidence";

type Topic = components["schemas"]["Topic"];
type Citation = components["schemas"]["Citation"];
type TopicValidity = components["schemas"]["TopicValidity"];
type DocumentValidity = components["schemas"]["DocumentValidity"];
type VersionValidity = components["schemas"]["VersionValidity"];
type VersionChange = components["schemas"]["VersionChange"];

const statusLabels: Record<VersionValidity["status"], string> = {
  em_vigor: "Em vigor na data",
  fase_declarada: "Em uso pela fase declarada (sem datas)",
  a_iniciar: "Vigência a iniciar",
  encerrada: "Vigência encerrada",
  substituida: "Substituída",
  sem_confirmacao: "Aplicação não confirmada",
};

function br(value?: string | null) {
  if (!value) return "não informada";
  const [y, m, d] = value.split("-");
  return `${d}/${m}/${y}`;
}

function CitationButton({ citation, onOpen, prefix = "Conferir" }: { citation: Citation; onOpen: (c: Citation) => void; prefix?: string }) {
  return <button className="link-button" onClick={() => onOpen(citation)}>{prefix} {citationLabel(citation)}</button>;
}

function CurrentBadge({ document }: { document: DocumentValidity }) {
  const current = document.versions.filter(v => document.current_version_ids.includes(v.version_id));
  if (current.length === 1) {
    const v = current[0];
    return <span className={`badge ${v.status}`}>Em vigor, versão {v.version || "sem número"}
      {v.status === "fase_declarada" ? " · datas não informadas" : ""}</span>;
  }
  if (current.length > 1) return <span className="badge sem_confirmacao">Mais de uma edição aplicável</span>;
  const upcoming = document.versions.find(v => v.status === "a_iniciar");
  if (upcoming) return <span className="badge a_iniciar">A iniciar em {br(upcoming.valid_from)} · versão {upcoming.version}</span>;
  return <span className="badge encerrada">Sem edição aplicável</span>;
}

function VersionRow({ version, onOpen }: { version: VersionValidity; onOpen: (c: Citation) => void }) {
  return <li className="version">
    <p><strong>Versão {version.version || "sem número"}</strong> · <span className={`badge ${version.status}`}>{statusLabels[version.status]}</span></p>
    <dl className="facts">
      <div><dt>Fase declarada</dt><dd>{version.declared_phase || "não declarada"}</dd></div>
      <div><dt>Vigência documentada</dt><dd>{version.valid_from || version.valid_until
        ? `${br(version.valid_from)} a ${br(version.valid_until)}` : "não informada no cabeçalho"}</dd></div>
      <div><dt>Substituição</dt><dd>{version.superseded_by.length
        ? version.superseded_by.map(s => `pela versão ${s.version}${s.in_effect ? ` desde ${br(s.valid_from)}` : s.valid_from ? ` a partir de ${br(s.valid_from)}` : " (início não documentado)"}`).join("; ")
        : version.supersedes.length ? `substitui a versão ${version.supersedes.map(s => s.version).join(", ")}` : "nenhuma declarada"}</dd></div>
    </dl>
    <p>{version.explanation}</p>
    <div className="citations">
      {version.header_citation && <CitationButton citation={version.header_citation} onOpen={onOpen} prefix="Cabeçalho:" />}
      {[...version.superseded_by, ...version.supersedes].filter(s => s.citation).map(s =>
        <CitationButton key={`${s.version_id}-${s.citation!.passage_id}`} citation={s.citation!} onOpen={onOpen} prefix="Declaração de substituição:" />)}
    </div>
  </li>;
}

function DocumentCard({ document, onOpen }: { document: DocumentValidity; onOpen: (c: Citation) => void }) {
  const precedence = document.precedence.filter(p => p.applicable);
  return <article className="document">
    <h3>{document.code || "Sem código"} · {document.title}</h3>
    <p><CurrentBadge document={document} /> <span className="layer">Camada: {document.document_layer || "não identificada"}</span>
      {document.document_type ? <span className="layer"> · {document.document_type}</span> : null}</p>
    {document.notice && <p className="notice" role="note">{document.notice}</p>}
    {document.links.length > 0 && <p>Vinculado a: {document.links.map(l => l.document_id ? l.code : `${l.code} (fora do acervo)`).join(", ")}</p>}
    {precedence.map(p => <div className="precedence" key={p.citation.passage_id}>
      <p>Precedência documentada: em divergência, prevalece a <strong>{p.prevailing_code}</strong>
        {p.prevailing_document_id ? "" : " (documento fora do acervo)"}.</p>
      <CitationButton citation={p.citation} onOpen={onOpen} />
    </div>)}
    <details>
      <summary>Versões e fontes ({document.versions.length})</summary>
      <ul className="versions">{document.versions.map(v => <VersionRow key={v.version_id} version={v} onOpen={onOpen} />)}</ul>
    </details>
  </article>;
}

function ChangeCard({ change, onOpen }: { change: VersionChange; onOpen: (c: Citation) => void }) {
  return <article className="change">
    <h4>{change.code}: {change.summary}</h4>
    <p className="change-values"><span>v{change.from_version}: {change.before_text}</span> → <span>v{change.to_version}: {change.after_text}</span></p>
    <p className="muted">Mudança entre versões do mesmo documento. Não é divergência entre fontes aplicáveis: a versão {change.from_version} foi substituída.</p>
    {change.note && <p className="notice">{change.note}</p>}
    <div className="citations">
      {change.before_citations.map(c => <CitationButton key={c.passage_id + c.excerpt} citation={c} onOpen={onOpen} prefix="Antes:" />)}
      {change.after_citations.map(c => <CitationButton key={c.passage_id + c.excerpt} citation={c} onOpen={onOpen} prefix="Depois:" />)}
    </div>
  </article>;
}

export function ValidityPanel({ topics }: { topics: Topic[] }) {
  const [topic, setTopic] = useState("");
  const [date, setDate] = useState("");
  const [result, setResult] = useState<TopicValidity | null>(null);
  const [evidence, setEvidence] = useState<Citation | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const evidencePanel = useRef<HTMLElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { if (evidence) evidencePanel.current?.focus(); }, [evidence]);
  async function load(event?: FormEvent) {
    event?.preventDefault();
    const topicId = topic || topics[0]?.id;
    if (!topicId) return;
    setBusy(true); setError("");
    try {
      const params = new URLSearchParams({ topic_id: topicId });
      if (date) params.set("reference_date", date);
      const response = await fetch(`/api/vigencia?${params}`);
      if (!response.ok) throw new Error("Não foi possível carregar a vigência do tema.");
      setResult(await response.json()); setEvidence(null);
    } catch (e) { setError(e instanceof Error ? e.message : "Não foi possível carregar a vigência."); }
    finally { setBusy(false); }
  }
  return <section aria-labelledby="validity-title">
    <h2 id="validity-title">Vigência, camadas e versões</h2>
    <p>Fase declarada, datas de vigência e substituição aparecem separadas. O rótulo “Vigente” não prova aplicação em qualquer data.</p>
    <form onSubmit={load}>
      <div className="query-filters">
        <label>Tema<select disabled={busy || !topics.length} value={topic || topics[0]?.id || ""} onChange={e => setTopic(e.target.value)}>
          {!topics.length && <option value="">Nenhum tema disponível</option>}
          {topics.map(t => <option value={t.id} key={t.id}>{t.name}</option>)}
        </select></label>
        <label>Data de referência<input type="date" value={date} disabled={busy} onChange={e => setDate(e.target.value)} /></label>
      </div>
      <button disabled={busy || !topics.length}>{busy ? "Carregando…" : "Ver vigência"}</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {result && <div aria-live="polite">
      <h3 ref={heading} tabIndex={-1}>Situação em {br(result.reference_date)}</h3>
      {result.documents.length === 0 && <p>Nenhuma versão publicada neste tema.</p>}
      {result.documents.map(d => <DocumentCard key={d.document_id} document={d} onOpen={setEvidence} />)}
      {result.changes.length > 0 && <>
        <h3>Mudanças entre versões</h3>
        {result.changes.map(c => <ChangeCard key={c.key} change={c} onOpen={setEvidence} />)}
      </>}
      {evidence && <EvidencePanel ref={evidencePanel} evidence={evidence} closeLabel="Voltar à vigência"
        onClose={() => { setEvidence(null); heading.current?.focus(); }} />}
    </div>}
  </section>;
}
