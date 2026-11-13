// Regressões da revisão da PR #40 (Gestão). Executar: npm test
import assert from "node:assert/strict";
import { test } from "node:test";
import { createLatest, retryOutcome } from "../src/managementState.ts";

const id = "00000000-0000-4000-8000-000000000012";

test("retry com HTTP 202 e status failed mostra o erro e não anuncia reenfileiramento", () => {
  const outcome = retryOutcome({ version_id: id, status: "failed", duplicate: true, error: "Conflito de edição legada." });
  assert.equal(outcome.kind, "failed");
  assert.equal(outcome.message, "Conflito de edição legada.");
  assert.doesNotMatch(outcome.message, /fila/);
});

test("retry com status failed sem motivo usa mensagem de falha", () => {
  const outcome = retryOutcome({ version_id: id, status: "failed", duplicate: true, error: null });
  assert.equal(outcome.kind, "failed");
  assert.match(outcome.message, /não foi recolocado/);
});

test("retry com status queued confirma o reenfileiramento", () => {
  const outcome = retryOutcome({ version_id: id, status: "queued", duplicate: true, error: null });
  assert.equal(outcome.kind, "queued");
  assert.match(outcome.message, /recolocado na fila/);
});

test("retry de versão já pronta não diz que reenviou", () => {
  const outcome = retryOutcome({ version_id: id, status: "ready", duplicate: true, error: null });
  assert.equal(outcome.kind, "unchanged");
  assert.doesNotMatch(outcome.message, /recolocado/);
});

test("nova requisição cancela a anterior e só a mais recente vale", () => {
  const latest = createLatest();
  const first = latest.begin("tema-a");
  const second = latest.begin("tema-a");
  assert.equal(first.signal.aborted, true);
  assert.equal(latest.isCurrent(first, "tema-a"), false);
  assert.equal(latest.isCurrent(second, "tema-a"), true);
});

test("resposta do tema anterior é descartada após trocar de tema", () => {
  const latest = createLatest();
  const request = latest.begin("tema-a");
  // O tema mudou enquanto a requisição estava em andamento.
  assert.equal(latest.isCurrent(request, "tema-b"), false);
});

test("resposta lenta de upload/retry não sobrescreve a lista do tema atual", async () => {
  const latest = createLatest();
  let current = "tema-a";
  const shown: string[] = [];
  const respond = (key: string, delay: number) => new Promise<string>(resolve => setTimeout(() => resolve(key), delay));
  async function load() {
    const request = latest.begin(current);
    const body = await respond(request.key, request.key === "tema-a" ? 30 : 5);
    if (latest.isCurrent(request, current)) shown.push(body);
  }
  const slow = load();          // ex.: recarga após upload no tema A
  current = "tema-b";           // pessoa troca de tema
  const fast = load();          // carga do tema B
  await Promise.all([slow, fast]);
  assert.deepEqual(shown, ["tema-b"]);
});

test("cancel invalida a requisição em andamento (desmontagem)", () => {
  const latest = createLatest();
  const request = latest.begin("tema-a");
  latest.cancel();
  assert.equal(latest.isCurrent(request, "tema-a"), false);
});
