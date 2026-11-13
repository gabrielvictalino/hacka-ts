import type { components } from "../../packages/contracts";

type Calculation = NonNullable<components["schemas"]["QuestionRequest"]["calculation"]>;
type Rule = Calculation["rule"];
export type CalculationDraft = {
  rule: Rule | "";
  amount: string;
  teamSize: string;
  absences: string;
  startDate: string;
  registeredOn: string;
  receivedOn: string;
  holidays: string[];
};

export function emptyCalculation(rule: Rule | "" = ""): CalculationDraft {
  return { rule, amount: "", teamSize: "", absences: "", startDate: "", registeredOn: "", receivedOn: "", holidays: [] };
}

function number(value: string, label: string, min: number, max: number, integer = false): number {
  const parsed = Number(value);
  if (!value.trim() || !Number.isFinite(parsed) || parsed < min || parsed > max || (integer && !Number.isInteger(parsed))) {
    throw new Error(`Informe ${label} válido${integer ? ", em número inteiro" : ""}.`);
  }
  return parsed;
}

function date(value: string, label: string): string {
  const parsed = new Date(`${value}T00:00:00Z`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(parsed.valueOf()) || parsed.toISOString().slice(0, 10) !== value) {
    throw new Error(`Informe uma data válida para ${label}.`);
  }
  return value;
}

export function buildCalculation(draft: CalculationDraft): Calculation | null {
  switch (draft.rule) {
    case "": return null;
    case "ferias.prazos": {
      if (draft.holidays.length > 366) throw new Error("Informe até 366 feriados.");
      return {
        rule: draft.rule,
        start_date: date(draft.startDate, "o início das férias"),
        request_registered_on: draft.registeredOn ? date(draft.registeredOn, "o registro da solicitação") : null,
        notice_received_on: draft.receivedOn ? date(draft.receivedOn, "o recebimento do aviso") : null,
        holidays: [...new Set(draft.holidays.map(value => date(value, "cada feriado")))],
      };
    }
    case "ferias.ausencia_simultanea":
      return { rule: draft.rule, team_size: number(draft.teamSize, "o tamanho da equipe", 1, 100000, true) };
    case "ferias.dias_por_faltas":
      return { rule: draft.rule, absences: number(draft.absences, "o total de faltas", 0, 366, true) };
    case "ferias.ressarcimento":
    case "inovacao.alcada":
      return { rule: draft.rule, amount: number(draft.amount, "um valor em reais", 0.01, 1000000000) };
    case "inovacao.orcamento":
    case "inovacao.pagamento_premiacao":
      return { rule: draft.rule };
  }
}

export function CalculationFields({ value, onChange, disabled }: {
  value: CalculationDraft;
  onChange: (value: CalculationDraft) => void;
  disabled: boolean;
}) {
  const patch = (updates: Partial<CalculationDraft>) => onChange({ ...value, ...updates });
  return <fieldset className="calculation-fields" disabled={disabled}>
    <legend>Cálculo com explicação (opcional)</legend>
    <label>Regra de cálculo<select value={value.rule}
      onChange={event => onChange(emptyCalculation(event.target.value as Rule | ""))}>
      <option value="">Sem cálculo · consultar documentos</option>
      <optgroup label="Férias">
        <option value="ferias.prazos">Prazos de férias</option>
        <option value="ferias.ausencia_simultanea">Pessoas de férias ao mesmo tempo</option>
        <option value="ferias.dias_por_faltas">Dias de férias por faltas injustificadas</option>
        <option value="ferias.ressarcimento">Limite de ressarcimento</option>
      </optgroup>
      <optgroup label="Inovação">
        <option value="inovacao.alcada">Alçada de aprovação</option>
        <option value="inovacao.orcamento">Composição do orçamento</option>
        <option value="inovacao.pagamento_premiacao">Prazo de pagamento das premiações</option>
      </optgroup>
    </select></label>
    {value.rule && <p>Selecione o tema correspondente. A consulta explicará esta regra com os parâmetros abaixo e as fontes disponíveis.</p>}
    {(value.rule === "ferias.ressarcimento" || value.rule === "inovacao.alcada") &&
      <label>{value.rule === "ferias.ressarcimento" ? "Despesa comprovada (R$)" : "Gasto de prototipagem por ideia (R$)"}
        <input type="number" required min="0.01" max="1000000000" step="0.01" inputMode="decimal"
          value={value.amount} onChange={event => patch({ amount: event.target.value })} />
      </label>}
    {value.rule === "ferias.ausencia_simultanea" && <label>Tamanho da equipe
      <input type="number" required min="1" max="100000" step="1" inputMode="numeric"
        value={value.teamSize} onChange={event => patch({ teamSize: event.target.value })} />
    </label>}
    {value.rule === "ferias.dias_por_faltas" && <label>Faltas injustificadas no período aquisitivo
      <input type="number" required min="0" max="366" step="1" inputMode="numeric"
        value={value.absences} onChange={event => patch({ absences: event.target.value })} />
    </label>}
    {value.rule === "ferias.prazos" && <>
      <label>Início das férias<input type="date" required value={value.startDate}
        onChange={event => patch({ startDate: event.target.value })} /></label>
      <label>Registro da solicitação (opcional)<input type="date" value={value.registeredOn}
        onChange={event => patch({ registeredOn: event.target.value })} /></label>
      <label>Recebimento do aviso (opcional)<input type="date" value={value.receivedOn}
        onChange={event => patch({ receivedOn: event.target.value })} /></label>
      <p>Informe os feriados da sede para a contagem de dias úteis. Sem feriados informados, serão excluídos apenas sábados e domingos.</p>
      {value.holidays.map((holiday, index) => <div className="holiday-row" key={index}>
        <label>Feriado {index + 1}<input type="date" required value={holiday}
          onChange={event => patch({ holidays: value.holidays.map((kept, at) => at === index ? event.target.value : kept) })} /></label>
        <button type="button" onClick={() => patch({ holidays: value.holidays.filter((_, at) => at !== index) })}
          aria-label={`Remover feriado ${index + 1}`}>Remover</button>
      </div>)}
      <button type="button" disabled={value.holidays.length >= 366}
        onClick={() => patch({ holidays: [...value.holidays, ""] })}>Adicionar feriado</button>
    </>}
    {(value.rule === "inovacao.orcamento" || value.rule === "inovacao.pagamento_premiacao") &&
      <p>Esta regra usa os fatos curados do acervo e não exige parâmetros adicionais.</p>}
  </fieldset>;
}
