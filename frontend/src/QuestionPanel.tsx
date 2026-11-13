import { createPortal } from "react-dom";
import { profileExperience } from "./profilePresentation";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { components } from "../../packages/contracts";
import { buildCalculation, CalculationFields, emptyCalculation } from "./CalculationFields";
import { DivergenceNotices } from "./DivergencePanel";
import { EvidencePanel, citationLabel } from "./Evidence";
import { INTERN_QUERY, INTERN_VIEW, internPassages } from "./views";

type Topic = components["schemas"]["Topic"];
type Result = components["schemas"]["QuestionResponse"];
type Citation = components["schemas"]["Citation"];
type Perspective = components["schemas"]["Perspective"];
const statuses = { supported: "Sustentada por trechos", partial: "Resposta parcial", insufficient: "Sem evidência suficiente", divergent: "Divergência" };

function Gaps({ gaps }: { gaps: string[] }) {
  return <><h3>Pontos sem confirmação</h3><ul>{gaps.map((gap, index) => <li key={`${index}-${gap}`}>{gap}</li>)}</ul></>;
}

export function QuestionPanel({ topics, view, userName, homeVersion }: { topics: Topic[]; view: string; userName: string; homeVersion: number }) {
  const presentation = profileExperience[view === "Gestor" ? "gestor" : view === "Diretoria ou apoio" ? "diretoria" : view === INTERN_VIEW ? "estagiario" : "empregado"];
  const [topicDetail, setTopicDetail] = useState(false);
  const [topic, setTopic] = useState("");
  const [question, setQuestion] = useState("");
  const [perspective, setPerspective] = useState("");
  const [area, setArea] = useState("");
  const [date, setDate] = useState("");
  const [calculation, setCalculation] = useState(emptyCalculation);
  const [askedQuestion, setAskedQuestion] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  useEffect(() => { setResult(null); setTopicDetail(false); }, [homeVersion]);
  const [context, setContext] = useState("");
  // Visão usada naquela consulta; trocar o "Ver para" depois não altera um resultado já exibido.
  const [resultView, setResultView] = useState("");
  const [interns, setInterns] = useState<{ topic: string; passages: Citation[] } | null>(null);
  const [internEvidence, setInternEvidence] = useState<Citation | null>(null);
  const [internBusy, setInternBusy] = useState(false);
  const [internError, setInternError] = useState("");
  const internPanel = useRef<HTMLElement>(null);
  const internHeading = useRef<HTMLHeadingElement>(null);
  const topicId = topic || topics[0]?.id || "";
  const topicName = topics.find(t => t.id === topicId)?.name || "";
  const internKey = `${topicId}|${view}`;
  const currentInternKey = useRef(internKey);
  currentInternKey.current = internKey;
  useEffect(() => { setInterns(null); setInternEvidence(null); setInternError(""); }, [internKey]);
  useEffect(() => { if (internEvidence) internPanel.current?.focus(); }, [internEvidence]);
  async function loadInterns() {
    const askedTopic = topicId, askedName = topicName, askedKey = internKey;
    const stillCurrent = () => currentInternKey.current === askedKey;
    setInternBusy(true); setInternError("");
    try {
      const response = await fetch("/perguntar", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic_id: askedTopic, question: INTERN_QUERY, reference_date: date || null }),
      });
      if (!response.ok) throw new Error("Não foi possível consultar o tema. Tente novamente.");
      const passages = internPassages(await response.json());
      if (!stillCurrent()) return;
      setInterns({ topic: askedName, passages });
      setInternEvidence(null);
    } catch (e) {
      if (stillCurrent()) setInternError(e instanceof Error ? e.message : "Não foi possível consultar o tema.");
    } finally { setInternBusy(false); }
  }
  const [evidence, setEvidence] = useState<Citation | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const evidencePanel = useRef<HTMLElement>(null);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { if (evidence) evidencePanel.current?.focus(); }, [evidence]);
  // Só parcial e insuficiente têm trechos que não confirmam a resposta; "divergent" mostra as evidências em conflito.
  const unconfirmed = result?.status === "partial" || result?.status === "insufficient";
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    const askedView = view;
    try {
      const requestedCalculation = buildCalculation(calculation);
      const response = await fetch("/perguntar", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic_id: topic || topics[0]?.id, question,
          ...(requestedCalculation ? {} : { perspective: perspective || null }), reference_date: date || null,
          filters: { area: area.trim() || null }, calculation: requestedCalculation }),
      });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(typeof body.detail === "string" ? body.detail : "Verifique os campos da consulta.");
      }
      setResult(await response.json()); setAskedQuestion(question); setEvidence(null);
      setContext(`${topics.find(t => t.id === (topic || topics[0]?.id))?.name} · ${question}`);
      setResultView(askedView);
    } catch (e) { setError(e instanceof Error ? e.message : "Não foi possível consultar. Tente novamente."); }
    finally { setBusy(false); }
  }
  function renderSearch() {
    const form = <form className={result || topicDetail ? "question-form search-form" : "question-form"} onSubmit={submit}>
      <label className="sr-only" htmlFor="acervo-question">Pergunta</label>
      <div className="ask"><textarea id="acervo-question" required maxLength={4000} rows={1} value={question} disabled={busy}
        onChange={e => setQuestion(e.target.value)} placeholder={result ? "Faça outra pergunta…" : presentation.placeholder} /><button className="primary" disabled={busy || !topics.length || !question.trim()}>{busy ? "Consultando…" : "Perguntar"}</button></div>
      <details className="query-options">
        <summary>Opções da consulta · {topicName || "Selecione um tema"}</summary>
        <label>Tema<select required disabled={busy || !topics.length} value={topic || topics[0]?.id || ""}
          onChange={e => { setTopic(e.target.value); setCalculation(emptyCalculation()); }}>
          {!topics.length && <option value="">Nenhum tema disponível</option>}
          {topics.map(t => <option value={t.id} key={t.id}>{t.name}</option>)}
        </select></label>
      <div className="query-filters">
        <label>Perspectiva<select value={calculation.rule ? "" : perspective} disabled={busy || !!calculation.rule}
          aria-describedby={calculation.rule ? "calculation-perspective-help" : undefined}
          onChange={e => setPerspective(e.target.value as Perspective)}>
          <option value="">{calculation.rule ? "Definida pela regra" : "Todas"}</option><option value="deadline">Prazos</option><option value="value">Valores</option>
          <option value="obligation" disabled>Obrigações · em breve</option><option value="risk" disabled>Riscos · em breve</option>
        </select></label>
        <label>Área<input value={area} maxLength={200} disabled={busy} onChange={e => setArea(e.target.value)} placeholder="Ex.: GGC" /></label>
        <label>Data de referência<input type="date" value={date} disabled={busy} onChange={e => setDate(e.target.value)} /></label>
      </div>
      {calculation.rule && <p id="calculation-perspective-help">A regra escolhida define os fatos usados no cálculo. A perspectiva será aplicada novamente ao consultar sem cálculo.</p>}
      <CalculationFields value={calculation} onChange={setCalculation} disabled={busy || !topics.length} />
      </details>
    </form>;
    const header = document.getElementById("header-query");
    return (result || topicDetail) && header ? createPortal(form, header) : form;
  }
  return <section className={result ? "question-page has-answer" : "question-page"} aria-label="Consulta ao acervo">
    {!result && !topicDetail ? <div className="hero"><h1>Olá, {userName}!<br /><span>{presentation.greeting}</span></h1>{"description" in presentation && <p>{presentation.description}</p>}</div> : <><div className="page-back"><button className="link" onClick={() => { setResult(null); setTopicDetail(false); }}>← Voltar ao início</button></div><h1 className="answer-question">{result ? askedQuestion : topicName}</h1>{!result && <nav className="tabs" aria-label="Perspectivas da consulta">{[["", "Todas"], ["deadline", "Prazos"], ["value", "Valores"]].map(([value, label]) => <button key={value} type="button" aria-pressed={perspective === value} disabled={!!calculation.rule} onClick={() => setPerspective(value as Perspective)}>{label}</button>)}</nav>}</>}
    {view === INTERN_VIEW && <div className="intern-view" aria-labelledby="intern-title">
      <h3 id="intern-title" ref={internHeading} tabIndex={-1}>Visão de estagiário ou aprendiz</h3>
      <p>Mostra só o que os documentos do tema dizem sobre estagiários e aprendizes, com a fonte.</p>
      <button type="button" disabled={internBusy || !topicId} onClick={loadInterns}>
        {internBusy ? "Consultando…" : `Ver o que ${topicName || "o tema"} diz sobre estagiários e aprendizes`}</button>
      {internError && <p role="alert">{internError}</p>}
      {interns && <div aria-live="polite">
        {interns.passages.length > 0
          ? <p>Trechos de {interns.topic} que mencionam estagiários ou aprendizes. O IPBOT não completa regras para esta
            visão: o que não aparece nesses trechos não foi encontrado nos documentos do tema.</p>
          : <p>Nenhum trecho de {interns.topic} encontrado na busca menciona estagiários ou aprendizes. O IPBOT não
            completa regras para esta visão.</p>}
        {interns.passages.map((c, at) => <article className="claim" key={`${at}-${c.passage_id}`}>
          <blockquote>{c.excerpt}</blockquote>
          <button onClick={() => setInternEvidence(c)}>Conferir {citationLabel(c)}</button>
        </article>)}
        {internEvidence && <EvidencePanel ref={internPanel} evidence={internEvidence} closeLabel="Voltar à visão"
          onClose={() => { setInternEvidence(null); internHeading.current?.focus(); }} />}
      </div>}
    </div>}
    {renderSearch()}
    {!result && topicDetail && <section className="panel stack"><h2>Consulte {topicName}</h2><p>Faça uma pergunta sobre este tema na busca acima. A resposta usa os documentos do acervo e apresenta as fontes para conferência.</p><div className="row">{presentation.suggestions.map(text => <button className="chip" type="button" key={text} onClick={() => { setQuestion(text); document.getElementById("acervo-question")?.focus(); }}>{text}</button>)}</div></section>}
    {!result && !topicDetail && <>
      <div className="row suggested-questions">{presentation.suggestions.map(text => <button type="button" className="chip" key={text} onClick={() => { setQuestion(text); document.getElementById("acervo-question")?.focus(); }}>{text}</button>)}</div>
      <section className="topics"><h2>O que você precisa consultar?</h2><div className={"grid profile-topics " + (topics.length === 2 ? "two" : "")}>
        {topics.map(t => { const key = /f[eé]rias/i.test(t.name) ? "ferias" : /inova|ideia/i.test(t.name) ? "ideias" : /loca|cowork/i.test(t.name) ? "coworking" : ""; const copy = presentation.topics.find(item => item[2] === key); return <button type="button" className="tile" key={t.id} onClick={() => { setTopic(t.id); setTopicDetail(true); setCalculation(emptyCalculation()); }}>
          <span className="topic-icon" aria-hidden="true"><svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">{key === "ferias" ? <><rect x="3" y="5" width="18" height="16" rx="3" /><path d="M8 3v4M16 3v4M3 10h18" /></> : key === "ideias" ? <path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.5 1 2.5h6c0-1 .3-1.8 1-2.5A6 6 0 0 0 12 3Z" /> : <><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 7h2m4 0h2M8 11h2m4 0h2M10 21v-6h4v6" /></>}</svg></span>
          <span className="topic-copy"><strong>{copy?.[0] || t.name}</strong><small>{copy?.[1] || "Consulte as orientações e as fontes disponíveis neste tema."}</small></span><span className="topic-open">Abrir <span aria-hidden="true">→</span></span>
        </button>; })}
      </div>{!topics.length && <p>Nenhum tema importado. Peça à Gestão do acervo para importar os documentos.</p>}</section>
    </>}
    {error && <p role="alert">{error}</p>}
    {result && <div className="panel accent answer-block" aria-live="polite">
      {/* Resposta primeiro: situação, aviso curto e afirmações com a fonte logo abaixo. */}
      <h3 ref={resultHeading} tabIndex={-1}>{statuses[result.status]}</h3>
      {result.notice && <p role="status" className="notice">{result.notice}</p>}
      <DivergenceNotices notices={result.divergence_notices ?? []} />
      {/* Sem sustentação completa, a lacuna vem antes dos trechos para não ser lida como resposta. */}
      {unconfirmed && result.gaps.length > 0 && <Gaps gaps={result.gaps} />}
      {result.claims.length === 0 && <p>Nenhuma afirmação foi sustentada pelos trechos do tema.</p>}
      {unconfirmed && result.claims.length > 0 && <p className="muted">Trechos relacionados encontrados no tema. Eles não confirmam os pontos acima.</p>}
      {result.claims.map((claim, index) => <article className="claim" key={index}>
        {claim.calculation_step != null && <p>Resultado calculado · passo {claim.calculation_step + 1}</p>}
        <blockquote>{claim.text}</blockquote>
        <div className="answer-evidence"><strong>Evidência</strong>{claim.citations.map((c, at) => <button key={`${at}-${c.passage_id}`} onClick={() => setEvidence(c)}>
          Conferir {c.code || c.title} · {c.version || "versão não identificada"} · p. {c.physical_page}{c.section ? ` · ${c.section}` : ""}
        </button>)}</div>
      </article>)}
      {!unconfirmed && result.gaps.length > 0 && <Gaps gaps={result.gaps} />}
      <p className="muted">{context}{resultView ? ` · Visão: ${resultView}` : ""}</p>
      <p className="muted">{result.mode === "extractive" ? "Modo extrativo" : "Seleção de trechos por modelo"} · Referência: {result.reference_date}</p>
      <p className="muted">{result.calculation
        ? "Os resultados foram calculados a partir das regras publicadas. Confira a memória de cálculo, as premissas e as fontes."
        : "Os trechos são literais. A correspondência textual não confirma interpretações além do que a fonte declara."}</p>
      {result.passages.length > 0 && <details><summary>Todas as fontes recuperadas ({result.passages.length})</summary>
        <ul>{result.passages.map((c, at) => <li key={`${at}-${c.passage_id}`}><button onClick={() => setEvidence(c)}>
          {c.code || c.title} · {c.version || "versão não identificada"} · p. {c.physical_page}
        </button></li>)}</ul>
      </details>}
      {result.calculation && <>
        {(result.calculation.warnings ?? []).map((warning, at) => <p role="status" key={`${at}-${warning}`}>{warning}</p>)}
        {(result.calculation.assumptions?.length ?? 0) > 0 && <><h3>Premissas do cálculo</h3>
          <ul>{result.calculation.assumptions?.map((assumption, at) => <li key={`${at}-${assumption}`}>{assumption}</li>)}</ul></>}
      </>}
      {evidence && <EvidencePanel ref={evidencePanel} evidence={evidence} closeLabel="Voltar à resposta"
        onClose={() => { setEvidence(null); resultHeading.current?.focus(); }} />}
    </div>}
  </section>;
}
