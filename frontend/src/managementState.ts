// Regras da Gestão sem dependência de React, para testes de regressão (npm test).
import type { components } from "../../packages/contracts";

type IngestionResult = components["schemas"]["IngestionResult"];

export type RetryOutcome = { kind: "queued" | "failed" | "unchanged"; message: string };

/**
 * Interpreta o IngestionResult de POST /api/documents/{id}/retry. O HTTP 202 não garante reenfileiramento:
 * uma fonte legada em conflito volta com status "failed" e não é reprocessada.
 */
export function retryOutcome(result: IngestionResult): RetryOutcome {
  if (result.status === "failed") {
    return { kind: "failed", message: result.error || "O arquivo continua com falha e não foi recolocado na fila." };
  }
  if (result.status === "queued") return { kind: "queued", message: "Arquivo recolocado na fila de processamento." };
  const state = result.status === "ready" ? "já está pronto para consulta" : "já está em processamento";
  return { kind: "unchanged", message: `Nada foi reenviado: o arquivo ${state}.` };
}

export type LatestRequest = { id: number; key: string; signal: AbortSignal };

/**
 * Mantém só a requisição mais recente: uma nova cancela a anterior, e uma resposta só vale se ainda for
 * a mais recente e se a chave (o tema) for a atual. Evita listas de outro tema e sobreposição do polling.
 */
export function createLatest() {
  let seq = 0;
  let controller: AbortController | null = null;
  return {
    begin(key: string): LatestRequest {
      controller?.abort();
      controller = new AbortController();
      seq += 1;
      return { id: seq, key, signal: controller.signal };
    },
    isCurrent(request: LatestRequest, currentKey: string): boolean {
      return request.id === seq && request.key === currentKey && !request.signal.aborted;
    },
    cancel() {
      controller?.abort();
      controller = null;
      seq += 1;
    },
  };
}
