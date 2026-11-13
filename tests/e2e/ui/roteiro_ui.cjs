// Roteiro de interface da #12 e da revisão da PR #40 no Chromium headless. Ver tests/e2e/README.md.
// Contas fictícias do SSO simulado. Não imprime cookies nem tokens.
const { chromium } = require("playwright");

const path = require("node:path");
const BASE = process.env.IPBOT_BASE_URL || "http://127.0.0.1:5173";
const SHOTS = process.env.IPBOT_E2E_SHOTS || "";
const FILES = process.env.IPBOT_E2E_FILES || path.join(__dirname, "arquivos");
const ROOT = path.resolve(__dirname, "../../..");
// Acervo importado: "referencia" (acervo do desafio, não versionado) ou "sintetico" (tests/e2e/acervo_sintetico.py).
const NG_PAGES = { referencia: 10, sintetico: 4 };
const ACERVO = process.env.IPBOT_E2E_ACERVO || "referencia";
// Onde rodar a simulação de conflito legado: "dev-local" (scripts/dev-local.sh) ou "compose" (serviço api).
const RUNNER = process.env.IPBOT_E2E_RUNNER || "dev-local";
if (!(ACERVO in NG_PAGES) || !["dev-local", "compose"].includes(RUNNER)) {
  console.log("IPBOT_E2E_ACERVO deve ser referencia ou sintetico; IPBOT_E2E_RUNNER, dev-local ou compose");
  process.exit(2);
}
const results = [];
function check(name, ok, detail = "") {
  results.push(ok);
  console.log(`${ok ? "OK   " : "FALHA"} ${name}${detail ? " · " + detail : ""}`);
}

async function enter(page, name) {
  await page.getByRole("button", { name }).click();
  await page.locator(".session").filter({ hasText: name }).waitFor();
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const consoleErrors = [];
  // O 401 de /eu sem sessão é esperado: é como o app descobre que ainda não há conta.
  page.on("console", m => {
    if (m.type() === "error" && !m.text().includes("status of 401")) consoleErrors.push(m.text());
  });

  await page.goto(BASE);
  await page.getByRole("heading", { name: "Escolha uma conta de demonstração" }).waitFor();
  check("Sem sessão, oferece só o simulador de SSO", true);
  check("Não há formulário de login ou senha", (await page.locator("input[type=password]").count()) === 0);
  check("Sem sessão, a navegação de áreas não aparece", (await page.getByRole("navigation", { name: "Áreas do IPBOT" }).count()) === 0);

  // Gestão do acervo: navegação com as duas áreas.
  await enter(page, "Gestão do acervo");
  const nav = page.getByRole("navigation", { name: "Áreas do IPBOT" });
  check("Gestão vê as abas Consulta e Gestão", (await nav.getByRole("button").allInnerTexts()).join(",") === "Consulta,Gestão");
  check("Consulta é a área inicial", (await nav.getByRole("button", { name: "Consulta" }).getAttribute("aria-current")) === "page");

  // Consulta AC-01 com evidência.
  const question = page.getByRole("region", { name: "Perguntar ao acervo" });
  await question.getByLabel("Tema").selectOption({ label: "Férias" });
  await question.getByLabel("Pergunta").fill("Com quantos dias de antecedência devo pedir férias?");
  await question.getByLabel("Data de referência").fill("2026-11-12");
  await question.getByRole("button", { name: "Perguntar" }).click();
  const heading = question.getByRole("heading", { name: "Sustentada por trechos" });
  await heading.waitFor();
  check("AC-01 mostra a resposta sustentada", true);
  const order = await question.locator("[aria-live=polite] > *").evaluateAll(nodes => nodes.map(n => n.className || n.tagName));
  const firstClaim = order.indexOf("claim"), firstMeta = order.indexOf("muted");
  check("Resposta vem antes dos metadados", firstClaim > -1 && firstClaim < firstMeta, `afirmação na posição ${firstClaim}, metadados na ${firstMeta}`);
  const cite = question.locator(".claim button").filter({ hasText: "4.3.1" }).first();
  check("Fonte logo abaixo da afirmação (NG_111 p. 2 · 4.3.1)", (await cite.count()) === 1, await cite.innerText().catch(() => ""));
  await cite.click();
  const evidence = question.getByRole("complementary", { name: "Evidência selecionada" });
  await evidence.waitFor();
  check("Painel de evidência recebe o foco", await evidence.evaluate(el => document.activeElement === el));
  const href = await evidence.getByRole("link", { name: "Abrir PDF nesta página" }).getAttribute("href");
  check("Link abre o original na página física citada", /\/api\/documents\/[0-9a-f-]+\/file#page=2$/.test(href || ""), href || "");
  const pdf = await page.request.get(BASE + (href || "").split("#")[0]);
  check("O PDF citado abre com a sessão", pdf.status() === 200 && (pdf.headers()["content-type"] || "").startsWith("application/pdf"));
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, "consulta-desktop.png"), fullPage: true });
  await evidence.getByRole("button", { name: "Voltar à resposta" }).click();
  check("Voltar à resposta devolve o foco ao resultado", await heading.evaluate(el => document.activeElement === el));

  // Trocar para Gestão e voltar sem perder o resultado.
  await nav.getByRole("button", { name: "Gestão" }).click();
  const management = page.getByRole("region", { name: "Gestão · Documentos do acervo" });
  await management.waitFor();
  check("Aba Gestão mostra a área de documentos", await management.isVisible());
  check("Consulta fica oculta na Gestão", !(await question.isVisible()));

  // Upload em lote: PDF válido e PDF sem texto.
  await management.getByRole("combobox").first().selectOption({ label: "Férias" });
  await management.getByLabel("Arquivos PDF").setInputFiles([
    path.join(FILES, "interface-valido.pdf"), path.join(FILES, "interface-sem-texto.pdf")]);
  check("Seleção mostra a quantidade de arquivos", await management.getByText("2 arquivo(s) selecionado(s) para Férias.").isVisible());
  await management.getByRole("button", { name: "Enviar para processamento" }).click();
  await management.getByRole("heading", { name: "Resultado do envio" }).waitFor();
  const lines = await management.locator(".upload-result").allInnerTexts();
  check("Resultado por arquivo após o envio", lines.length === 2, lines.join(" | "));
  const failedCard = management.locator(".managed-version").filter({ hasText: "interface-sem-texto.pdf" }).first();
  await failedCard.getByText("Falha no processamento").waitFor({ timeout: 30000 });
  check("Falha aparece com o motivo", (await failedCard.innerText()).includes("sem texto extraível"));
  const okCard = management.locator(".managed-version").filter({ hasText: "interface-valido.pdf" }).first();
  await okCard.getByText("Pronto para consulta").waitFor({ timeout: 30000 });
  check("PDF válido fica pronto pela atualização automática", true);
  const ngCard = management.locator(".managed-version").filter({ hasText: "NG_111 · Férias" }).filter({ hasText: /Versão\s*3\.0\.0/ }).first();
  const ngText = await ngCard.innerText();
  const pages = `${NG_PAGES[ACERVO]} de ${NG_PAGES[ACERVO]} páginas`;
  const ngOk = ["3.0.0", "Norma Geral", "Vigente", pages].every(t => ngText.includes(t));
  check("Lista mostra versão, tipo, fase e páginas", ngOk, ngOk ? `NG_111 v3.0.0 · Norma Geral · Vigente · ${pages}` : ngText.replace(/\s+/g, " "));
  await failedCard.getByRole("button", { name: "Tentar novamente" }).click();
  await management.getByText("Arquivo recolocado na fila de processamento.").waitFor();
  check("Tentar novamente recoloca o arquivo na fila", true);
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, "gestao-desktop.png"), fullPage: true });

  // Teclado: voltar à Consulta pela aba.
  await nav.getByRole("button", { name: "Consulta" }).focus();
  await page.keyboard.press("Enter");
  check("Teclado ativa a aba Consulta", await question.isVisible());
  check("Resultado da Consulta foi preservado", await heading.isVisible());

  // Empregado: sem Gestão; Ver para muda só a apresentação.
  await page.getByRole("button", { name: "Pessoa empregada" }).click();
  await page.locator(".session").filter({ hasText: "Pessoa empregada" }).waitFor();
  check("Empregado não vê a aba Gestão", (await nav.getByRole("button", { name: "Gestão" }).count()) === 0);
  check("Empregado não tem a área de upload", (await page.getByLabel("Arquivos PDF").count()) === 0);
  await page.getByLabel("Perspectiva exibida").selectOption("Estagiário ou aprendiz");
  check("Ver para oferece voltar à visão da conta", await page.getByRole("button", { name: "Voltar à minha visão" }).isVisible());
  const q2 = page.getByRole("region", { name: "Perguntar ao acervo" });
  await q2.getByLabel("Pergunta").fill("Estagiários seguem a norma de férias?");
  await q2.getByRole("button", { name: "Perguntar" }).click();
  await q2.locator("[aria-live=polite] h3").first().waitFor();
  check("Resultado registra a visão escolhida", (await q2.locator(".muted").first().innerText()).includes("Visão: Estagiário ou aprendiz"));
  const upload = await page.request.post(`${BASE}/api/documents/batch`, { multipart: { topic_id: "00000000-0000-0000-0000-000000000000" } });
  check("Ver para não concede upload (API responde 403)", upload.status() === 403);

  // Tela de celular.
  const mobile = await browser.newPage({ viewport: { width: 375, height: 740 } });
  await mobile.goto(BASE);
  await mobile.getByRole("button", { name: "Gestão do acervo" }).click();
  await mobile.getByRole("navigation", { name: "Áreas do IPBOT" }).waitFor();
  const overflowConsulta = await mobile.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  await mobile.getByRole("button", { name: "Gestão", exact: true }).click();
  await mobile.locator(".managed-version").first().waitFor();
  const overflowGestao = await mobile.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check("Sem rolagem horizontal no celular", overflowConsulta <= 0 && overflowGestao <= 0, `Consulta ${overflowConsulta}px, Gestão ${overflowGestao}px`);
  if (SHOTS) await mobile.screenshot({ path: path.join(SHOTS, "gestao-celular.png"), fullPage: true });

  // Integração com a #15: detalhes só na Gestão, aviso curto na Consulta.
  const ac03 = "A solicitação foi aprovada 32 dias antes das férias. Quando a GGC emite o aviso?";
  await page.getByRole("button", { name: "Gestão do acervo" }).click();
  await page.locator(".session").filter({ hasText: "Gestão do acervo" }).waitFor();
  await nav.getByRole("button", { name: "Gestão" }).click();
  const divergences = page.getByRole("region", { name: "Gestão · Divergências entre fontes" });
  check("Painel de divergências fica na área de Gestão", await divergences.isVisible());
  await divergences.getByRole("combobox").first().selectOption({ label: "Férias" });
  await divergences.getByLabel("Data de referência").fill("2026-11-13");
  await divergences.getByRole("button", { name: "Ver divergências" }).click();
  await divergences.locator(".divergence-card").first().waitFor();
  const card = await divergences.locator(".divergence-card").first().innerText();
  check("Gestão vê o AC-03 com as duas fontes e a precedência", ["AC-03", "4.5.3", "8.4.2", "Precedência declarada"].every(t => card.includes(t)));
  await nav.getByRole("button", { name: "Consulta" }).click();
  check("Painel de divergências some ao voltar à Consulta", !(await divergences.isVisible()));

  await page.getByRole("button", { name: "Pessoa empregada" }).click();
  await page.locator(".session").filter({ hasText: "Pessoa empregada" }).waitFor();
  check("Empregado não tem o painel de divergências", (await page.getByRole("region", { name: "Gestão · Divergências entre fontes" }).count()) === 0);
  const q3 = page.getByRole("region", { name: "Perguntar ao acervo" });
  await q3.getByRole("combobox").first().selectOption({ label: "Férias" });
  await q3.getByLabel("Pergunta").fill(ac03);
  await q3.getByLabel("Data de referência", { exact: true }).fill("2026-11-13");
  await q3.getByRole("button", { name: "Perguntar" }).click();
  await q3.locator("[aria-live=polite] h3").first().waitFor();
  const notice = q3.locator(".notice.divergence");
  await notice.first().waitFor({ timeout: 15000 }).catch(() => {});
  check("Consulta do AC-03 mostra só o aviso curto", (await notice.count()) > 0 && (await q3.locator(".divergence-card").count()) === 0,
    (await notice.first().innerText().catch(() => "sem aviso")).slice(0, 120));
  const order3 = await q3.locator("[aria-live=polite] > *").evaluateAll(n => n.map(x => x.className || x.tagName));
  check("Aviso curto aparece antes das afirmações", order3.indexOf("divergence-notices") > -1
    && order3.indexOf("divergence-notices") < order3.indexOf("claim"), order3.slice(0, 5).join(","));

  // Revisão da PR #40.
  // (a) A visão fica com a consulta: trocar o "Ver para" depois não muda o resultado já exibido.
  await page.getByLabel("Perspectiva exibida").selectOption("Diretoria ou apoio");
  await q3.getByRole("button", { name: "Perguntar" }).click();
  await q3.locator("[aria-live=polite] h3").first().waitFor();
  await page.waitForTimeout(500);
  await page.getByLabel("Perspectiva exibida").selectOption("Gestor");
  const meta = await q3.locator("[aria-live=polite] .muted").allInnerTexts();
  check("Resultado mantém a visão usada na consulta", meta.some(t => t.includes("Visão: Diretoria ou apoio")) && !meta.some(t => t.includes("Visão: Gestor")),
    meta.find(t => t.includes("Visão")) || "");

  // (b) Visão de estagiário ou aprendiz: mostra o item 4.12 da NG_111 com a fonte, sem inventar regra.
  await page.getByLabel("Perspectiva exibida").selectOption("Estagiário ou aprendiz");
  const intern = q3.locator(".intern-view");
  await intern.getByRole("button", { name: /Ver o que .* diz sobre estagiários e aprendizes/ }).click();
  await intern.locator(".claim").first().waitFor({ timeout: 20000 });
  const internText = await intern.innerText();
  check("Visão de estagiário mostra o item 4.12 com a fonte", internText.includes("Estagiários e aprendizes não são regidos")
    && /NG_111 · 3\.0\.0 · p\. 4 · 4\.12/.test(internText));
  check("Visão de estagiário declara que não completa regras", internText.includes("O IPBOT não completa regras para esta"));
  await intern.getByRole("button", { name: /Conferir NG_111/ }).first().click();
  check("Fonte da visão de estagiário abre no painel de evidência",
    await intern.getByRole("complementary", { name: "Evidência selecionada" }).isVisible());

  // (c) Retry com HTTP 202 e status "failed" mostra o erro e não anuncia reenfileiramento.
  const { execFileSync } = require("node:child_process");
  const legacyScript = path.join(__dirname, "legacy_conflict.py");
  // No Compose, o script vai pela entrada padrão: tests/ não é montado no container da API.
  const run = (arg) => (RUNNER === "compose"
    ? execFileSync("docker", ["compose", "exec", "-T", "-e", `IPBOT_E2E_ALLOW_DB=${process.env.IPBOT_E2E_ALLOW_DB || ""}`,
      "api", "python", "-", arg], { cwd: ROOT, input: require("node:fs").readFileSync(legacyScript) })
    : execFileSync(path.join(ROOT, "scripts/dev-local.sh"), ["run", ".venv/bin/python", "tests/e2e/ui/legacy_conflict.py", arg],
      { cwd: ROOT, env: process.env })).toString().trim();
  const conflictId = run("set");
  try {
    await page.getByRole("button", { name: "Gestão do acervo" }).click();
    await page.locator(".session").filter({ hasText: "Gestão do acervo" }).waitFor();
    await nav.getByRole("button", { name: "Gestão" }).click();
    const mgmt = page.getByRole("region", { name: "Gestão · Documentos do acervo" });
    await mgmt.getByRole("combobox").first().selectOption({ label: "Férias" });
    const legacy = mgmt.locator(".managed-version").filter({ has: page.locator(`a[href="/api/documents/${conflictId}/file#page=1"]`) });
    await legacy.getByRole("button", { name: "Tentar novamente" }).click();
    await legacy.getByRole("alert").waitFor();
    const statusText = await mgmt.locator("p[role=status]").last().innerText();
    check("Retry com 202 e status failed mostra o erro", (await legacy.getByRole("alert").innerText()).includes("Conflito de edição legada"));
    check("Retry com status failed não anuncia reenfileiramento", !statusText.includes("recolocado"), statusText || "(status vazio)");
  } finally {
    console.log("      " + run("restore"));
  }

  check("Sem erros no console do navegador", consoleErrors.length === 0, consoleErrors.slice(0, 3).join(" | "));
  await browser.close();
  console.log(`\n${results.filter(Boolean).length}/${results.length} verificações passaram`);
  process.exit(results.every(Boolean) ? 0 : 1);
})().catch(e => { console.log("ERRO", String(e).split("\n").slice(0, 6).join(" | ")); process.exit(1); });
