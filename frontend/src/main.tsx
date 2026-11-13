import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import type { components } from "../../packages/contracts";
import "./style.css";
import { QuestionPanel } from "./QuestionPanel";

type Identity = components["schemas"]["Identity"];
type DemoAssertion = components["schemas"]["DemoAssertion"];
type Topic = components["schemas"]["Topic"];

const views = ["Empregado", "Gestor", "Diretoria ou apoio", "Estagiário ou aprendiz"];

function defaultView(identity: Identity) {
  return identity.role === "empregado" ? views[0] : views[1];
}

function App() {
  const [users, setUsers] = useState<Identity[]>([]);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState("");
  async function loadTopics(signal?: AbortSignal) {
    const response = await fetch("/api/topics", { signal });
    if (!response.ok) throw new Error("Não foi possível carregar os temas.");
    setTopics(await response.json());
  }
  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    setBusy(true);
    Promise.all([
      fetch("/api/auth/demo/users", { signal }).then(async r => {
        if (r.status === 404) return;
        if (!r.ok) throw new Error("Simulador de identidade indisponível.");
        setUsers(await r.json());
      }),
      fetch("/eu", { signal }).then(async r => {
        if (r.status === 401) return;
        if (!r.ok) throw new Error("Não foi possível verificar a sessão.");
        const current: Identity = await r.json();
        setIdentity(current);
        setView(defaultView(current));
        await loadTopics(signal);
      }),
    ]).catch(e => { if (!signal.aborted) setError(String(e)); })
      .finally(() => { if (!signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, []);
  async function selectUser(subject: string) {
    setBusy(true); setError("");
    try {
      const assertion = await fetch("/api/auth/demo/assertion", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: subject }),
      });
      if (!assertion.ok) throw new Error("Não foi possível selecionar a conta de demonstração.");
      const { token }: DemoAssertion = await assertion.json();
      const session = await fetch("/auth/callback", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (!session.ok) throw new Error("Não foi possível iniciar a sessão de demonstração.");
      const current: Identity = await session.json();
      setIdentity(current);
      setView(defaultView(current));
      setTopics([]);
      await loadTopics();
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }
  return <main>
    <p className="eyebrow">IPBOT · Ambiente de desenvolvimento</p>
    <h1>Acervo e fontes verificáveis</h1>
    <p>Base inicial para organizar documentos e preservar suas evidências.</p>
    <section aria-labelledby="identity-title">
      <h2 id="identity-title">Identidade de demonstração</h2>
      {users.length > 0 && <p>SSO simulado com contas fictícias. Selecione uma conta para verificar o acesso.</p>}
      <div className="accounts">{users.map(user => <button disabled={busy} key={user.subject}
        onClick={() => selectUser(user.subject)}>{user.name}</button>)}</div>
      {identity && <p role="status">Sessão: {identity.name} · {identity.role}</p>}
      {error && <p role="alert">{error}</p>}
    </section>
    {identity && <section aria-labelledby="view-title">
      <h2 id="view-title">Perspectiva da Consulta</h2>
      <label>Ver para{" "}
        <select value={view} onChange={event => setView(event.target.value)}>
          {views.map(option => <option key={option}>{option}</option>)}
        </select>
      </label>{" "}
      {view !== defaultView(identity) && <button onClick={() => setView(defaultView(identity))}>Voltar à minha visão</button>}
    </section>}
    {identity?.permissions.includes("documents:ingest") && <section aria-labelledby="management-title">
      <h2 id="management-title">Gestão do acervo</h2>
      <p>Esta conta tem acesso às operações de upload e aos detalhes dos alertas.</p>
    </section>}
    {identity && <QuestionPanel key={identity.subject} topics={topics} />}
    {identity && <section aria-labelledby="topics-title"><h2 id="topics-title">Temas do acervo</h2>
      {topics.length ? <ul>{topics.map(topic => <li key={topic.id}>{topic.name}</li>)}</ul>
        : <p>Nenhum tema importado. Importe o acervo para começar.</p>}
    </section>}
  </main>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
