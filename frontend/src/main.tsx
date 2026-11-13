import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import type { components } from "../../packages/contracts";
import "./clause.css";
import "./document-reader.css";
import "./visual.css";
import { ManagementPanel } from "./ManagementPanel";
import { QuestionPanel } from "./QuestionPanel";
import { ValidityPanel } from "./ValidityPanel";
import { VIEWS } from "./views";
import { DivergencePanel } from "./DivergencePanel";

type Identity = components["schemas"]["Identity"];
type DemoAssertion = components["schemas"]["DemoAssertion"];
type Topic = components["schemas"]["Topic"];
type Area = "consulta" | "gestao" | "vigencia" | "divergencias";

const views: readonly string[] = VIEWS;

function defaultView(identity: Identity) {
  return identity.role === "empregado" ? views[0] : views[1];
}

function can(identity: Identity | null, permission: Identity["permissions"][number]) {
  return identity?.permissions.includes(permission) ?? false;
}

// A área de Gestão reúne upload (documents:ingest) e detalhes de divergências (alerts:read-details);
// cada painel exige a própria permissão, e a aba aparece com qualquer uma delas.
function canManage(identity: Identity | null) {
  return can(identity, "documents:ingest") || can(identity, "alerts:read-details");
}

function App() {
  const [homeVersion, setHomeVersion] = useState(0);
  const [showIdentity, setShowIdentity] = useState(false);
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
    setArea(a => ((a === "gestao" || a === "divergencias") && !canManage(current) ? "consulta" : a));
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
      setShowIdentity(false);
      setTopics([]);
      await loadTopics();
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }
  if (!identity || showIdentity) return <main className="auth">
    <section className="auth-brand" aria-label="BBTS Clause">
      <span className="auth-circle auth-circle-large" aria-hidden="true" />
      <span className="auth-circle auth-circle-small" aria-hidden="true" />
      <img className="auth-logo" src="/clause-logo-white.png" alt="BBTS Clause" />
      <div className="auth-pitch">
        <p className="auth-headline">Encontre a regra certa, <span>com a fonte na mão.</span></p>
        <p className="auth-lead">Pergunte em linguagem natural e consulte a orientação com o trecho da norma.</p>
      </div>
      <ul className="auth-points">
        <li><span className="auth-point-icon" aria-hidden="true"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3V4zM9 9h6M9 13h6" /></svg></span><span>Confira o documento, a página e o item de cada evidência.</span></li>
        <li><span className="auth-point-icon" aria-hidden="true"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7l8-4zM9 12l2 2 4-4" /></svg></span><span>Consulte a vigência das normas e identifique versões antigas.</span></li>
      </ul>
    </section>
    <section className="auth-form-side" aria-labelledby="identity-title">
      <div className="auth-form" aria-busy={busy}>
        <div><p className="eyebrow">SSO SIMULADO</p><h1 id="identity-title">Entrar na BBTS Clause</h1></div>
        {!checked && <p role="status">Verificando a sua conta…</p>}
        {checked && <>
          <p className="auth-description">{users.length > 0 ? "Escolha uma conta de demonstração para acessar o acervo. As contas são fictícias e simulam a identidade recebida pelo SSO." : "Não há sessão válida e o simulador de identidade está desativado. Procure o suporte para acessar o IPBOT."}</p>
          <div className="accounts auth-accounts">{users.map(user => <button disabled={busy} key={user.subject} onClick={() => selectUser(user.subject)}>
            <span className="account-avatar" aria-hidden="true">{user.name.slice(0, 1)}</span><span className="account-copy"><strong>{user.name}</strong><span>{user.role}</span></span><span aria-hidden="true">→</span>
          </button>)}</div>
          {busy && <p role="status">Iniciando sessão de demonstração…</p>}
        </>}
        {error && <p role="alert">{error}</p>}
      </div>
    </section>
  </main>;
  const management = canManage(identity);
  return <>
    <header>
      <div className="topbar">
        <a className="brand" href="#inicio" onClick={event => { event.preventDefault(); setArea("consulta"); setHomeVersion(value => value + 1); }}><img className="mark" src="/clause-logo-white.png" alt="BBTS Clause" />{area === "gestao" || area === "divergencias" ? <strong>Gestão</strong> : null}</a>
        <div id="header-query" hidden={area !== "consulta"} />
        <details className="profile">
          <summary className="avatar profile-trigger" aria-label="Perfil e SSO simulado">{identity.name.slice(0, 1)}</summary>
          <div className="profile-popup">
            <strong>{identity.name}</strong><span className="profile-role">{identity.role} · {identity.simulated ? "SSO simulado" : "Sessão ativa"}</span>
        <nav className="profile-links" aria-label="Áreas do IPBOT" onClick={event => event.currentTarget.closest("details")?.removeAttribute("open")}>
          <button aria-current={area === "consulta" ? "page" : undefined} onClick={() => setArea("consulta")}>Consulta</button>
          <button aria-current={area === "vigencia" ? "page" : undefined} onClick={() => setArea("vigencia")}>Vigência</button>
          {management && <button aria-current={area === "gestao" || area === "divergencias" ? "page" : undefined} onClick={() => setArea(can(identity, "documents:ingest") ? "gestao" : "divergencias")}>Gestão</button>}
        </nav>
            <label className="setting-field">Ver para<select value={view} onChange={event => setView(event.target.value)}>{views.map(option => <option key={option}>{option}</option>)}</select></label>
            {view !== defaultView(identity) && <button className="link" onClick={() => setView(defaultView(identity))}>Voltar à minha visão</button>}
            {users.length > 0 && <button className="profile-logout" onClick={() => setShowIdentity(true)}>Trocar conta · SSO simulado</button>}
          </div>
        </details>
      </div>
    </header>
    <main className="home-page">
      {error && <p role="alert">{error}</p>}
      <div hidden={area !== "consulta"}>
        <QuestionPanel key={identity.subject} topics={topics} view={view} userName={identity.name} homeVersion={homeVersion} />
      </div>
      <div hidden={area !== "vigencia"} className="screen-page stack">
        <div className="page-back"><button className="link" onClick={() => setArea("consulta")}>← Voltar ao início</button></div>
        <div><h1>Vigência e versões</h1><p>Consulte as normas aplicáveis e compare as versões do acervo.</p></div>
        <ValidityPanel key={`validity-${identity.subject}`} topics={topics} />
      </div>
      {management && <div hidden={area !== "gestao" && area !== "divergencias"} className="screen-page">
        <h1>{area === "divergencias" ? "Alertas" : "Documentos"}</h1>
        <p>{identity.name}, consulte as versões, envie documentos para processamento e acompanhe os alertas do acervo.</p>
        <nav className="tabs" aria-label="Seções da Gestão">
          {can(identity, "documents:ingest") && <button aria-pressed={area === "gestao"} onClick={() => setArea("gestao")}>Documentos</button>}
          {can(identity, "alerts:read-details") && <button aria-pressed={area === "divergencias"} onClick={() => setArea("divergencias")}>Alertas</button>}
        </nav>
        {can(identity, "documents:ingest") && <div hidden={area !== "gestao"}><ManagementPanel key={`management-${identity.subject}`} topics={topics} onTopicsChanged={() => loadTopics()} /></div>}
        {can(identity, "alerts:read-details") && <div hidden={area !== "divergencias"}><DivergencePanel key={`divergence-${identity.subject}`} topics={topics} /></div>}
      </div>}
      <footer>BBTS Clause · Orientações com fontes verificáveis.</footer>
    </main>
  </>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
