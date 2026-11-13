import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import type { components } from "../../packages/contracts";
import "./style.css";

type Identity = components["schemas"]["Identity"];
type Topic = components["schemas"]["Topic"];

function App() {
  const [users, setUsers] = useState<Identity[]>([]);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    fetch("/api/auth/demo/users").then(async r => {
      if (!r.ok) throw new Error("Simulador de identidade indisponível.");
      setUsers(await r.json());
    }).catch(e => setError(String(e)));
  }, []);
  async function selectUser(subject: string) {
    setBusy(true); setError("");
    try {
      const session = await fetch("/api/auth/demo/session", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: subject }),
      });
      if (!session.ok) throw new Error("Não foi possível iniciar a sessão de demonstração.");
      setIdentity(await session.json());
      const response = await fetch("/api/topics");
      if (!response.ok) throw new Error("Não foi possível carregar os temas.");
      setTopics(await response.json());
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }
  return <main>
    <p className="eyebrow">IPBOT · Ambiente de desenvolvimento</p>
    <h1>Acervo e fontes verificáveis</h1>
    <p>Base inicial para organizar documentos e preservar suas evidências.</p>
    <section aria-labelledby="identity-title">
      <h2 id="identity-title">Identidade de demonstração</h2>
      <p>Simulador de SSO com contas fictícias. Selecione uma conta para verificar o acesso.</p>
      <div className="accounts">{users.map(user => <button disabled={busy} key={user.subject}
        onClick={() => selectUser(user.subject)}>{user.name}</button>)}</div>
      {identity && <p role="status">Sessão: {identity.name} · {identity.role}</p>}
      {error && <p role="alert">{error}</p>}
    </section>
    {identity && <section aria-labelledby="topics-title"><h2 id="topics-title">Temas do acervo</h2>
      {topics.length ? <ul>{topics.map(topic => <li key={topic.id}>{topic.name}</li>)}</ul>
        : <p>Nenhum tema importado. Importe o acervo para começar.</p>}
    </section>}
  </main>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
