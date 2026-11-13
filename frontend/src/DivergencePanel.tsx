import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { components } from "../../packages/contracts";
import { EvidencePanel, citationLabel } from "./Evidence";

type Topic = components["schemas"]["Topic"];
type Citation = components["schemas"]["Citation"];
type TopicDivergences = components["schemas"]["TopicDivergences"];
type SourceDivergence = components["schemas"]["SourceDivergence"];
type DivergenceNotice = components["schemas"]["DivergenceNotice"];

const statusLabels: Record<SourceDivergence["status"], string> = {
  confirmed: "Divergência confirmada no cenário",
  possible: "Possível divergência · não confirmada",
  not_applicable: "Fora do cenário na data de referência",
};

function br(value: string) {
  const [y, m, d] = value.split("-");
  return `${d}/${m}/${y}`;
}

/** Aviso curto da Consulta: sem passagens, cenário ou precedência. */
export function DivergenceNotices({ notices }: { notices: DivergenceNotice[] }) {
  if (!notices.length) return null;
  return <div className="divergence-notices">
    {notices.map(n => <p key={n.key} className={`notice divergence ${n.status}`} role="note">{n.message}</p>)}
  </div>;
}

function DivergenceCard({ divergence, onOpen }: { divergence: SourceDivergence; onOpen: (c: Citation) => void }) {
  return <article className="divergence-card">
    <h4>{divergence.scenario_id} · {divergence.subject}</h4>
    <p><span className={`badge divergence ${divergence.status}`}>{statusLabels[divergence.status]}</span>{" "}
      <span className="layer">Curadoria manual · {divergence.curated_by} · revisada em {br(divergence.reviewed_on)}</span></p>
    <p>{divergence.status_explanation}</p>
    <dl className="facts">
      <div><dt>Pergunta de referência</dt><dd>{divergence.question}</dd></div>
      <div><dt>Cenário</dt><dd>{divergence.scenario}</dd></div>
      <div><dt>Condições de aplicação</dt><dd><ul>{divergence.conditions.map(c => <li key={c}>{c}</li>)}</ul></dd></div>
      <div><dt>Consequência</dt><dd>{divergence.consequence}</dd></div>
    </dl>
    <div className="passages">
      {divergence.guidances.map(g => <div className="passage" key={g.citation.passage_id}>
        <p><strong>{g.role}</strong>: {g.guidance}</p>
        <blockquote>{g.citation.excerpt}</blockquote>
        {!g.applicable && <p className="notice">{g.status === "fase_declarada"
          ? "Vigência sem data de início: aplicação não confirmada na data de referência."
          : "Edição sem aplicação na data de referência."}</p>}
        <button className="link-button" onClick={() => onOpen(g.citation)}>Conferir {citationLabel(g.citation)}</button>
      </div>)}
    </div>
    {divergence.precedence ? <div className="precedence">
      <p>Precedência declarada: prevalece a <strong>{divergence.precedence.prevailing_code}</strong>
        {divergence.precedence.prevailing_document_id ? "" : " (documento fora do acervo)"}. {divergence.precedence.statement}
        {" "}O IPBOT mostra a regra declarada e não escolhe uma das orientações.
        {!divergence.precedence.applicable && " A aplicação da edição que declara a precedência não está confirmada na data."}</p>
      <button className="link-button" onClick={() => onOpen(divergence.precedence!.citation)}>
        Conferir {citationLabel(divergence.precedence.citation)}</button>
    </div> : <p className="notice">Precedência entre as fontes não confirmada.</p>}
    {divergence.missing_information.length > 0 && <>
      <h5>Informação não confirmada</h5>
      <ul>{divergence.missing_information.map(m => <li key={m}>{m}</li>)}</ul>
    </>}
  </article>;
}

export function DivergencePanel({ topics }: { topics: Topic[] }) {
  const [topic, setTopic] = useState("");
  const [date, setDate] = useState("");
  const [result, setResult] = useState<TopicDivergences | null>(null);
  const [evidence, setEvidence] = useState<Citation | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const evidencePanel = useRef<HTMLElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { if (evidence) evidencePanel.current?.focus(); }, [evidence]);
  async function load(event: FormEvent) {
    event.preventDefault();
    const topicId = topic || topics[0]?.id;
    if (!topicId) return;
    setBusy(true); setError("");
    try {
      const params = new URLSearchParams({ topic_id: topicId });
      if (date) params.set("reference_date", date);
      const response = await fetch(`/api/divergencias?${params}`);
      if (response.status === 403) throw new Error("Os detalhes de divergências são reservados à Gestão do acervo.");
      if (!response.ok) throw new Error("Não foi possível carregar as divergências do tema.");
      setResult(await response.json()); setEvidence(null);
    } catch (e) { setError(e instanceof Error ? e.message : "Não foi possível carregar as divergências."); }
    finally { setBusy(false); }
  }
  return <section aria-labelledby="divergence-title">
    <h2 id="divergence-title">Gestão · Divergências entre fontes</h2>
    <p>Divergência entre fontes aplicáveis ao mesmo cenário. Mudanças entre versões do mesmo documento aparecem
      separadas, na vigência.</p>
    <form onSubmit={load}>
      <div className="query-filters">
        <label>Tema<select disabled={busy || !topics.length} value={topic || topics[0]?.id || ""} onChange={e => setTopic(e.target.value)}>
          {!topics.length && <option value="">Nenhum tema disponível</option>}
          {topics.map(t => <option value={t.id} key={t.id}>{t.name}</option>)}
        </select></label>
        <label>Data de referência<input type="date" value={date} disabled={busy} onChange={e => setDate(e.target.value)} /></label>
      </div>
      <button disabled={busy || !topics.length}>{busy ? "Carregando…" : "Ver divergências"}</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {result && <div aria-live="polite">
      <h3 ref={heading} tabIndex={-1}>Divergências em {br(result.reference_date)}</h3>
      <p className="notice" role="note">{result.curation_note}</p>
      {result.divergences.length === 0 && <p>Nenhuma divergência curada envolve as fontes publicadas neste tema.</p>}
      {result.divergences.map(d => <DivergenceCard key={d.key} divergence={d} onOpen={setEvidence} />)}
      {evidence && <EvidencePanel ref={evidencePanel} evidence={evidence} closeLabel="Voltar às divergências"
        onClose={() => { setEvidence(null); heading.current?.focus(); }} />}
    </div>}
  </section>;
}
