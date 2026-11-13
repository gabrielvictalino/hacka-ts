import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import type { components } from "../../packages/contracts";
import "./style.css";
import "./app.css";
import { ManagementPanel } from "./ManagementPanel";
import { QuestionPanel } from "./QuestionPanel";
import { ValidityPanel } from "./ValidityPanel";

type Identity = components["schemas"]["Identity"];
type DemoAssertion = components["schemas"]["DemoAssertion"];
type Topic = components["schemas"]["Topic"];
type Area = "consulta" | "gestao";

const views = ["Empregado", "Gestor", "Diretoria ou apoio", "Estagiário ou aprendiz"];

function defaultView(identity: Identity) {
  return identity.role === "empregado" ? views[0] : views[1];
}

function canManage(identity: Identity | null) {
  return identity?.permissions.includes("documents:ingest") ?? false;
}

function App() {
  const [users, setUsers] = useState<Identity[]>([]);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [checked, setChecked] = useState(false);
  const [view, setView] = useState("");
  const [area, setArea] = useState<Area>("consulta");
  async function loadTopics(signal?: AbortSignal) {
    const response = await fetch("/api/topics", { signal });
    if (!response.ok) throw new Error("Não foi possível carregar os temas.");
    setTopics(await response.json());
  }
  function start(current: Identity) {
    setIdentity(current);
    setView(defaultView(current));
    // A Gestão só existe para quem tem a permissão; a navegação não altera a sessão.
    setArea(a => (a === "gestao" && !canManage(current) ? "consulta" : a));
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
        start(await r.json());
        await loadTopics(signal);
      }),
    ]).catch(e => { if (!signal.aborted) setError(String(e)); })
      .finally(() => { if (!signal.aborted) { setBusy(false); setChecked(true); } });
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
      start(await session.json());
      setTopics([]);
      await loadTopics();
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }
  const management = canManage(identity);
  return <main>
    <header className="app-header">
      <p className="eyebrow">IPBOT</p>
      {identity && <p className="session" role="status">{identity.name} · {identity.role}
        {identity.simulated ? " · SSO simulado" : ""}</p>}
    </header>
    <h1>Acervo e fontes verificáveis</h1>
    {!checked && <p role="status">Verificando a sua conta…</p>}
    {error && <p role="alert">{error}</p>}
    {checked && (users.length > 0 || !identity) && <section aria-labelledby="identity-title" className="demo-identity">
      <h2 id="identity-title">{identity ? "Trocar conta de demonstração"
        : users.length > 0 ? "Escolha uma conta de demonstração" : "Conta não identificada"}</h2>
      {users.length > 0
        ? <p>SSO simulado com contas fictícias. Não é um provedor corporativo nem um formulário de login.</p>
        : <p>Não há sessão válida e o simulador de identidade está desativado. Procure o suporte para acessar o IPBOT.</p>}
      <div className="accounts">{users.map(user => <button disabled={busy} key={user.subject}
        aria-pressed={identity?.subject === user.subject}
        onClick={() => selectUser(user.subject)}>{user.name}</button>)}</div>
    </section>}
    {identity && <nav className="areas" aria-label="Áreas do IPBOT">
      <button className="area-tab" aria-current={area === "consulta" ? "page" : undefined}
        onClick={() => setArea("consulta")}>Consulta</button>
      {management && <button className="area-tab" aria-current={area === "gestao" ? "page" : undefined}
        onClick={() => setArea("gestao")}>Gestão</button>}
    </nav>}
    {identity && <div hidden={area !== "consulta"}>
      <section aria-labelledby="view-title">
        <h2 id="view-title">Ver para</h2>
        <label className="inline-field">Perspectiva exibida{" "}
          <select value={view} onChange={event => setView(event.target.value)}>
            {views.map(option => <option key={option}>{option}</option>)}
          </select>
        </label>{" "}
        {view !== defaultView(identity) && <button onClick={() => setView(defaultView(identity))}>Voltar à minha visão</button>}
        <p className="muted">Muda só a apresentação. As permissões continuam as da sua conta.</p>
      </section>
      {topics.length === 0 && <section><p>Nenhum tema importado. {management
        ? "Envie documentos pela Gestão ou importe o acervo." : "Peça à Gestão do acervo para importar os documentos."}</p></section>}
      {identity && <QuestionPanel key={identity.subject} topics={topics} view={view} />}
      {identity && <ValidityPanel key={`validity-${identity.subject}`} topics={topics} />}
    </div>}
    {identity && management && <div hidden={area !== "gestao"}>
      <ManagementPanel key={`management-${identity.subject}`} topics={topics} onTopicsChanged={() => loadTopics()} />
    </div>}
  </main>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
