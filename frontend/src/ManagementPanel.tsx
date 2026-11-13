import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { components } from "../../packages/contracts";

type Topic = components["schemas"]["Topic"];
type DocumentVersion = components["schemas"]["DocumentVersion"];
type BatchFileResult = components["schemas"]["BatchFileResult"];
type IngestionResult = components["schemas"]["IngestionResult"];

// Mesmo limite do backend (MAX_UPLOAD_BYTES); o servidor continua sendo a validação definitiva.
const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
const POLL_MS = 2000;

const statusLabels: Record<DocumentVersion["status"], string> = {
  queued: "Na fila",
  processing: "Processando",
  ready: "Pronto para consulta",
  failed: "Falha no processamento",
};

function br(value?: string | null) {
  if (!value) return null;
  const [y, m, d] = value.split("-");
  return `${d}/${m}/${y}`;
}

async function detail(response: Response, fallback: string) {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : fallback;
  } catch {
    return fallback;
  }
}

function permissionError(response: Response) {
  if (response.status === 401) return "Sessão expirada. Selecione novamente a conta para continuar.";
  if (response.status === 403) return "Esta conta não tem permissão para operações da Gestão.";
  return null;
}

function ResultLine({ item }: { item: BatchFileResult }) {
  if (item.error || !item.result) {
    return <li className="upload-result failed"><strong>{item.filename}</strong>: {item.error || "Não processado."}</li>;
  }
  const result: IngestionResult = item.result;
  const text = result.status === "failed" ? `falha · ${result.error || "verifique a lista abaixo"}`
    : result.duplicate ? "arquivo já enviado; versão existente reutilizada"
    : "enviado e colocado na fila de processamento";
  return <li className={`upload-result ${result.status}`}><strong>{item.filename}</strong>: {text}</li>;
}

function VersionCard({ version, onRetry, retrying, retryError }: {
  version: DocumentVersion;
  onRetry: (id: string) => void;
  retrying: boolean;
  retryError?: string;
}) {
  const progress = version.page_count ? `${version.processed_pages} de ${version.page_count} páginas`
    : version.status === "ready" ? null : `${version.processed_pages} páginas processadas`;
  const period = version.valid_from || version.valid_until
    ? `${br(version.valid_from) || "início não informado"} a ${br(version.valid_until) || "fim não informado"}`
    : "não informada no cabeçalho";
  return <li className="managed-version">
    <h4>{version.code || "Sem código"} · {version.title}</h4>
    <p><span className={`badge status-${version.status}`}>{statusLabels[version.status]}</span>
      {progress && <span className="layer"> · {progress}</span>}</p>
    <dl className="facts">
      <div><dt>Versão</dt><dd>{version.version || "não identificada"}</dd></div>
      <div><dt>Tipo</dt><dd>{version.document_type || "não identificado"}</dd></div>
      <div><dt>Fase declarada</dt><dd>{version.declared_phase || "não declarada"}</dd></div>
      <div><dt>Vigência documentada</dt><dd>{period}</dd></div>
      <div><dt>Arquivo</dt><dd className="filename">{version.filename}</dd></div>
    </dl>
    {version.status === "failed" && version.error && <p className="notice" role="note">{version.error}</p>}
    {retryError && <p role="alert">{retryError}</p>}
    <div className="citations">
      <a className="link-button" href={`/api/documents/${version.id}/file#page=1`} target="_blank" rel="noreferrer">
        Abrir PDF original</a>
      {version.status === "failed" && <button className="link-button" disabled={retrying}
        onClick={() => onRetry(version.id)}>{retrying ? "Reenviando…" : "Tentar novamente"}</button>}
    </div>
  </li>;
}

export function ManagementPanel({ topics, onTopicsChanged }: {
  topics: Topic[];
  onTopicsChanged: () => Promise<void>;
}) {
  const [topic, setTopic] = useState("");
  const [versions, setVersions] = useState<DocumentVersion[] | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [results, setResults] = useState<BatchFileResult[]>([]);
  const [newTopic, setNewTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [retrying, setRetrying] = useState<string | null>(null);
  const [retryErrors, setRetryErrors] = useState<Record<string, string>>({});
  const fileInput = useRef<HTMLInputElement>(null);
  const topicId = topic || topics[0]?.id || "";
  const topicName = topics.find(t => t.id === topicId)?.name;

  const load = useCallback(async (signal?: AbortSignal) => {
    if (!topicId) { setVersions(null); return; }
    setLoading(true);
    try {
      const response = await fetch(`/api/documents?${new URLSearchParams({ topic_id: topicId })}`, { signal });
      if (!response.ok) throw new Error(permissionError(response) || "Não foi possível carregar os documentos do tema.");
      setVersions(await response.json());
      setError("");
    } catch (e) {
      if (!signal?.aborted) setError(e instanceof Error ? e.message : "Não foi possível carregar os documentos.");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [topicId]);

  useEffect(() => {
    const controller = new AbortController();
    setVersions(null); setResults([]); setRetryErrors({});
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  // Acompanha o processamento enquanto houver arquivos na fila ou em extração.
  const pending = versions?.some(v => v.status === "queued" || v.status === "processing") ?? false;
  useEffect(() => {
    if (!pending) return;
    const controller = new AbortController();
    const timer = window.setInterval(() => load(controller.signal), POLL_MS);
    return () => { window.clearInterval(timer); controller.abort(); };
  }, [pending, load]);

  function choose(list: FileList | null) {
    setResults([]); setError("");
    setFiles(list ? Array.from(list) : []);
  }

  async function upload(event: FormEvent) {
    event.preventDefault();
    const accepted = files.filter(f => f.size <= MAX_UPLOAD_BYTES);
    const rejected = files.filter(f => f.size > MAX_UPLOAD_BYTES)
      .map(f => ({ filename: f.name, error: "Arquivo acima de 25 MiB; reduza o tamanho e envie novamente." }));
    if (!topicId || !accepted.length) { setResults(rejected); return; }
    setBusy(true); setError(""); setStatus(`Enviando ${accepted.length} arquivo(s)…`);
    try {
      const body = new FormData();
      body.append("topic_id", topicId);
      accepted.forEach(f => body.append("files", f, f.name));
      const response = await fetch("/api/documents/batch", { method: "POST", body });
      if (!response.ok) throw new Error(permissionError(response) || await detail(response, "Não foi possível enviar os arquivos."));
      const received: BatchFileResult[] = await response.json();
      setResults([...received, ...rejected]);
      setFiles([]);
      if (fileInput.current) fileInput.current.value = "";
      setStatus("Envio concluído. Acompanhe o processamento na lista abaixo.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível enviar os arquivos.");
      setStatus("");
    } finally {
      setBusy(false);
    }
  }

  async function retry(id: string) {
    setRetrying(id);
    setRetryErrors(current => { const next = { ...current }; delete next[id]; return next; });
    try {
      const response = await fetch(`/api/documents/${id}/retry`, { method: "POST" });
      if (!response.ok) {
        const message = permissionError(response) || await detail(response, "Não foi possível tentar novamente.");
        setRetryErrors(current => ({ ...current, [id]: message }));
        return;
      }
      setStatus("Arquivo recolocado na fila de processamento.");
      await load();
    } finally {
      setRetrying(null);
    }
  }

  async function createTopic(event: FormEvent) {
    event.preventDefault();
    const name = newTopic.trim();
    if (!name) return;
    setBusy(true); setError("");
    try {
      const response = await fetch("/api/topics", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }),
      });
      if (!response.ok) throw new Error(permissionError(response) || await detail(response, "Não foi possível criar o tema."));
      const created: Topic = await response.json();
      await onTopicsChanged();
      setTopic(created.id); setNewTopic("");
      setStatus(`Tema “${created.name}” disponível para envio.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível criar o tema.");
    } finally {
      setBusy(false);
    }
  }

  const failed = versions?.filter(v => v.status === "failed").length ?? 0;
  return <section aria-labelledby="management-title">
    <h2 id="management-title">Gestão · Documentos do acervo</h2>
    <p>Envie PDFs com texto pesquisável. Cada arquivo só entra na Consulta depois de concluir o processamento.</p>

    <form onSubmit={upload}>
      <div className="query-filters">
        <label>Tema<select disabled={busy || !topics.length} value={topicId} onChange={e => setTopic(e.target.value)}>
          {!topics.length && <option value="">Nenhum tema disponível</option>}
          {topics.map(t => <option value={t.id} key={t.id}>{t.name}</option>)}
        </select></label>
        <label>Arquivos PDF<input ref={fileInput} type="file" accept="application/pdf,.pdf" multiple
          disabled={busy || !topicId} onChange={e => choose(e.target.files)} aria-describedby="upload-help" /></label>
      </div>
      <p id="upload-help" className="muted">Selecione um ou vários arquivos. Limite de 25 MiB por PDF.</p>
      {files.length > 0 && <p>{files.length} arquivo(s) selecionado(s) para {topicName}.</p>}
      <button disabled={busy || !topicId || !files.length}>{busy ? "Enviando…" : "Enviar para processamento"}</button>
    </form>

    <details className="new-topic">
      <summary>Criar um novo tema</summary>
      <form onSubmit={createTopic}>
        <label>Nome do tema<input value={newTopic} maxLength={200} disabled={busy}
          onChange={e => setNewTopic(e.target.value)} placeholder="Ex.: Viagens a serviço" /></label>
        <button disabled={busy || !newTopic.trim()}>Criar tema</button>
      </form>
    </details>

    {error && <p role="alert">{error}</p>}
    <p role="status" className="muted">{status}</p>
    {results.length > 0 && <div aria-live="polite">
      <h3>Resultado do envio</h3>
      <ul className="upload-results">{results.map((item, index) => <ResultLine key={`${item.filename}-${index}`} item={item} />)}</ul>
    </div>}

    <h3>Documentos em {topicName || "nenhum tema"}</h3>
    {loading && versions === null && <p role="status">Carregando documentos…</p>}
    {versions && versions.length === 0 && <p>Nenhum documento neste tema. Envie um PDF para começar.</p>}
    {versions && versions.length > 0 && <>
      <p className="muted">{versions.length} versão(ões){failed ? ` · ${failed} com falha` : ""}
        {pending ? " · atualizando o processamento automaticamente" : ""}</p>
      <ul className="managed-versions">{versions.map(v => <VersionCard key={v.id} version={v} onRetry={retry}
        retrying={retrying === v.id} retryError={retryErrors[v.id]} />)}</ul>
    </>}
  </section>;
}
