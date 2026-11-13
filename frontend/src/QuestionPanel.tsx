import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { components } from "../../packages/contracts";
import { EvidencePanel } from "./Evidence";

type Topic = components["schemas"]["Topic"];
type Result = components["schemas"]["QuestionResponse"];
type Citation = components["schemas"]["Citation"];
type Perspective = components["schemas"]["Perspective"];
const statuses = { supported: "Sustentada por trechos", partial: "Resposta parcial", insufficient: "Sem evidência suficiente", divergent: "Divergência" };

export function QuestionPanel({ topics }: { topics: Topic[] }) {
  const [topic, setTopic] = useState("");
  const [question, setQuestion] = useState("");
  const [perspective, setPerspective] = useState("");
  const [area, setArea] = useState("");
  const [date, setDate] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [context, setContext] = useState("");
  const [evidence, setEvidence] = useState<Citation | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const evidencePanel = useRef<HTMLElement>(null);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { if (evidence) evidencePanel.current?.focus(); }, [evidence]);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const response = await fetch("/perguntar", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic_id: topic || topics[0]?.id, question,
          perspective: perspective || null, reference_date: date || null,
          filters: { area: area.trim() || null } }),
      });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(typeof body.detail === "string" ? body.detail : "Verifique os campos da consulta.");
      }
      setResult(await response.json()); setEvidence(null);
      setContext(`${topics.find(t => t.id === (topic || topics[0]?.id))?.name} · ${question}`);
    } catch (e) { setError(e instanceof Error ? e.message : "Não foi possível consultar. Tente novamente."); }
    finally { setBusy(false); }
  }
  return <section aria-labelledby="question-title">
    <h2 id="question-title">Perguntar ao acervo</h2>
    <form onSubmit={submit}>
      <label>Tema<select required disabled={busy || !topics.length} value={topic || topics[0]?.id || ""}
        onChange={e => setTopic(e.target.value)}>
        {!topics.length && <option value="">Nenhum tema disponível</option>}
        {topics.map(t => <option value={t.id} key={t.id}>{t.name}</option>)}
      </select></label>
      <label>Pergunta<textarea required maxLength={4000} value={question} disabled={busy}
        onChange={e => setQuestion(e.target.value)} placeholder="Qual o prazo para solicitar férias?" /></label>
      <div className="query-filters">
        <label>Perspectiva<select value={perspective} disabled={busy} onChange={e => setPerspective(e.target.value as Perspective)}>
          <option value="">Todas</option><option value="deadline">Prazos</option><option value="value">Valores</option>
          <option value="obligation" disabled>Obrigações · em breve</option><option value="risk" disabled>Riscos · em breve</option>
        </select></label>
        <label>Área<input value={area} maxLength={200} disabled={busy} onChange={e => setArea(e.target.value)} placeholder="Ex.: GGC" /></label>
        <label>Data de referência<input type="date" value={date} disabled={busy} onChange={e => setDate(e.target.value)} /></label>
      </div>
      <button disabled={busy || !topics.length || !question.trim()}>{busy ? "Consultando…" : "Perguntar"}</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {result && <div aria-live="polite">
      <h3 ref={resultHeading} tabIndex={-1}>{statuses[result.status]}</h3>
      <p>{context}</p>
      <p>{result.mode === "extractive" ? "Modo extrativo" : "Seleção de trechos por modelo"} · Referência: {result.reference_date}</p>
      <p>Os trechos são literais. A correspondência textual não confirma interpretações além do que a fonte declara.</p>
      {result.notice && <p role="status">{result.notice}</p>}
      {result.claims.map((claim, index) => <article className="claim" key={index}>
        <blockquote>{claim.text}</blockquote>
        {claim.citations.map(c => <button key={c.passage_id} onClick={() => setEvidence(c)}>
          Conferir {c.code || c.title} · {c.version || "versão não identificada"} · p. {c.physical_page}{c.section ? ` · ${c.section}` : ""}
        </button>)}
      </article>)}
      {result.passages.length > 0 && <details><summary>Todas as fontes recuperadas ({result.passages.length})</summary>
        <ul>{result.passages.map(c => <li key={c.passage_id}><button onClick={() => setEvidence(c)}>
          {c.code || c.title} · {c.version || "versão não identificada"} · p. {c.physical_page}
        </button></li>)}</ul>
      </details>}
      {result.gaps.length > 0 && <><h3>Pontos sem confirmação</h3><ul>{result.gaps.map(gap => <li key={gap}>{gap}</li>)}</ul></>}
      {evidence && <EvidencePanel ref={evidencePanel} evidence={evidence} closeLabel="Voltar à resposta"
        onClose={() => { setEvidence(null); resultHeading.current?.focus(); }} />}
    </div>}
  </section>;
}
