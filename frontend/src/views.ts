// "Ver para": a visão muda só a apresentação e acompanha a consulta; permissões vêm da sessão.
import type { components } from "../../packages/contracts";

type Citation = components["schemas"]["Citation"];
type QuestionResponse = components["schemas"]["QuestionResponse"];

export const VIEWS = ["Empregado", "Gestor", "Diretoria ou apoio", "Estagiário ou aprendiz"] as const;
export const INTERN_VIEW = "Estagiário ou aprendiz";
/** Pergunta enviada para localizar, no tema, os trechos sobre estagiários e aprendizes. */
export const INTERN_QUERY = "estagiários e aprendizes";

const INTERN_PATTERN = /estagi[aá]ri|aprendiz/i;

/** Verdadeiro só quando o trecho literal cita estagiários ou aprendizes. */
export function mentionsInterns(excerpt: string): boolean {
  return INTERN_PATTERN.test(excerpt);
}

/**
 * Trechos da resposta que citam estagiários ou aprendizes, sem repetir a mesma passagem.
 * Usa só a evidência devolvida pelo servidor; nenhuma regra é inferida.
 */
export function internPassages(result: QuestionResponse): Citation[] {
  const seen = new Set<string>();
  const all = [...result.claims.flatMap(claim => claim.citations), ...result.passages];
  return all.filter(c => {
    if (!mentionsInterns(c.excerpt) || seen.has(c.passage_id)) return false;
    seen.add(c.passage_id);
    return true;
  });
}
