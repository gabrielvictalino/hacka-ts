"""Fonte dos contratos Python, OpenAPI e tipos TypeScript gerados."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="allow")
    loc: list[str | int]
    msg: str
    type: str


class APIError(Contract):
    detail: str | list[ValidationIssue]


class Role(StrEnum):
    empregado = "empregado"
    gestor = "gestor"
    gestao = "gestao"


class Permission(StrEnum):
    read = "documents:read"
    ingest = "documents:ingest"
    curate = "facts:curate"
    read_alerts = "alerts:read-details"


class Identity(Contract):
    subject: str
    name: str
    role: Role
    permissions: list[Permission]
    simulated: bool


class DemoSessionRequest(Contract):
    user_id: str


class AuthCallbackRequest(Contract):
    token: str = Field(min_length=1, max_length=8192)


class DemoAssertion(Contract):
    token: str


class Topic(Contract):
    id: UUID
    name: str


class TopicRequest(Contract):
    name: str = Field(min_length=1, max_length=200, pattern=r"\S")


class IngestionResult(Contract):
    version_id: UUID
    status: Literal["queued", "processing", "ready", "failed"]
    duplicate: bool = False
    error: str | None = None


class BatchFileResult(Contract):
    filename: str
    result: IngestionResult | None = None
    error: str | None = None


class DocumentVersion(Contract):
    id: UUID
    document_id: UUID
    topic_id: UUID
    filename: str
    title: str
    code: str | None
    version: str | None
    document_type: str | None
    document_layer: str | None
    declared_phase: str | None
    valid_from: date | None
    valid_until: date | None
    linked_codes: list[str]
    processed_pages: int
    status: Literal["queued", "processing", "ready", "failed"]
    page_count: int | None
    error: str | None


class Citation(Contract):
    document_id: UUID
    document_type: str | None = None
    document_layer: str | None = None
    declared_phase: str | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    version_id: UUID
    passage_id: UUID
    title: str
    code: str | None = None
    version: str | None = None
    physical_page: int = Field(ge=1, description="Página física do PDF, começando em 1")
    excerpt: str = Field(min_length=1)
    section: str | None = None


class Perspective(StrEnum):
    deadline = "deadline"
    value = "value"
    obligation = "obligation"
    risk = "risk"


class QuestionFilters(Contract):
    area: str | None = Field(default=None, min_length=1, max_length=200)


class Claim(Contract):
    calculation_step: int | None = Field(default=None, ge=0, description="Índice do passo calculado pelo backend")
    text: str
    citations: list[Citation] = Field(min_length=1)


class Divergence(Contract):
    classification: Literal["confirmed", "possible"]
    reasoning: str
    missing_information: list[str]
    citations: list[Citation] = Field(min_length=2)


DivergenceStatus = Literal["confirmed", "possible", "not_applicable"]


class DivergenceNotice(Contract):
    """Aviso curto da Consulta; passagens, cenário e precedência ficam com a Gestão do acervo."""

    key: str
    kind: Literal["source_divergence"] = "source_divergence"
    subject: str
    status: Literal["confirmed", "possible"] = Field(description="possible: falta suporte para confirmar")
    codes: list[str] = Field(description="Documentos envolvidos")
    message: str


class CuratedFact(Contract):
    """Fato revisado manualmente; cada citação aponta para o trecho literal da edição publicada."""

    id: UUID
    key: str | None = Field(description="Identificador estável no catálogo de curadoria")
    topic_id: UUID
    topic: str
    category: Perspective
    attribute: str | None = Field(description="Atributo normalizado para comparar o mesmo fato entre fontes")
    area: str | None = Field(description="Unidade ou papel responsável, usado no filtro por área")
    statement: str
    responsible: str | None
    value: float | None = Field(
        description="Valor numérico para cálculos e gráficos; o texto da fonte fica em value_text"
    )
    value_text: str | None = Field(description="Valor como aparece na fonte, com a unidade original")
    unit: str | None
    starts_on: date | None = None
    ends_on: date | None = None
    conditions: str | None
    tags: list[str]
    curated_by: str
    curated_at: datetime
    citations: list[Citation] = Field(min_length=1)


class CurationItem(Contract):
    key: str
    status: Literal["published", "pending"]
    reason: str | None = None


class CurationReport(Contract):
    published: int
    pending: int
    items: list[CurationItem]


ValidityStatus = Literal["em_vigor", "fase_declarada", "a_iniciar", "encerrada", "substituida", "sem_confirmacao"]


class Succession(Contract):
    """Sucessão declarada pela edição sucessora; a anterior continua consultável como fonte histórica."""

    version_id: UUID = Field(description="A outra edição da relação")
    version: str | None
    valid_from: date | None
    in_effect: bool = Field(description="A sucessora já começou na data de referência")
    citation: Citation | None = Field(description="Trecho da sucessora que declara a substituição")


class VersionValidity(Contract):
    version_id: UUID
    version: str | None
    title: str
    declared_phase: str | None = Field(description="Rótulo impresso; não prova aplicação em uma data")
    valid_from: date | None
    valid_until: date | None
    linked_codes: list[str]
    status: ValidityStatus = Field(
        description="Situação na data de referência: em_vigor (intervalo documentado), fase_declarada (sem datas), "
        "a_iniciar, encerrada, substituida ou sem_confirmacao"
    )
    applicable: bool = Field(description="Elegível para respostas na data de referência")
    explanation: str
    superseded_by: list[Succession]
    supersedes: list[Succession]
    header_citation: Citation | None = Field(description="Cabeçalho com fase e vigência impressas")


class DocumentLink(Contract):
    code: str
    document_id: UUID | None = Field(description="Documento do mesmo tema; nulo quando não consta do acervo")


class PrecedenceDeclaration(Contract):
    prevailing_code: str
    prevailing_document_id: UUID | None
    applicable: bool = Field(description="A edição que declara a precedência é aplicável na data de referência")
    citation: Citation


class DocumentValidity(Contract):
    document_id: UUID
    code: str | None
    title: str
    document_type: str | None
    document_layer: str | None
    current_version_ids: list[UUID]
    notice: str | None
    links: list[DocumentLink]
    precedence: list[PrecedenceDeclaration]
    versions: list[VersionValidity]


class VersionChange(Contract):
    """Mudança curada entre edições do mesmo documento; não é divergência entre fontes aplicáveis."""

    key: str
    kind: Literal["version_change"] = "version_change"
    code: str
    attribute: str
    summary: str
    from_version: str
    to_version: str
    from_version_id: UUID | None
    to_version_id: UUID | None
    before_text: str
    after_text: str
    previous_available: bool = Field(description="O PDF da edição anterior consta do tema")
    in_effect: bool = Field(description="A edição nova é aplicável na data de referência")
    to_status: ValidityStatus = Field(description="Situação da edição nova na data de referência")
    to_valid_from: date | None = Field(description="Início documentado da edição nova")
    to_valid_until: date | None = Field(description="Fim documentado da edição nova")
    note: str | None
    before_citations: list[Citation]
    after_citations: list[Citation] = Field(min_length=1)


class TopicValidity(Contract):
    topic_id: UUID
    reference_date: date
    documents: list[DocumentValidity]
    changes: list[VersionChange]


class DivergentGuidance(Contract):
    role: str = Field(description="Camada da fonte no cenário, como norma geral ou procedimento vinculado")
    guidance: str = Field(description="Resumo da curadoria; o texto literal está na citação")
    status: ValidityStatus = Field(description="Situação da edição citada na data de referência")
    applicable: bool
    citation: Citation


class DeclaredPrecedence(Contract):
    prevailing_code: str
    prevailing_document_id: UUID | None = Field(description="Nulo quando o documento não consta do tema")
    statement: str
    applicable: bool = Field(description="A edição que declara a precedência é aplicável na data de referência")
    citation: Citation


class SourceDivergence(Contract):
    """Divergência entre fontes aplicáveis ao mesmo cenário; não é mudança histórica entre versões."""

    key: str
    kind: Literal["source_divergence"] = "source_divergence"
    scenario_id: str
    subject: str
    question: str
    scenario: str
    conditions: list[str]
    consequence: str
    status: DivergenceStatus = Field(
        description="confirmed: passagens localizadas e aplicáveis; possible: falta suporte para confirmar; "
        "not_applicable: alguma edição não se aplica na data de referência"
    )
    status_explanation: str
    missing_information: list[str]
    guidances: list[DivergentGuidance]
    precedence: DeclaredPrecedence | None = Field(description="Nula quando a declaração não foi localizada")
    curation: Literal["manual"] = "manual"
    curated_by: str
    reviewed_on: date


class TopicDivergences(Contract):
    topic_id: UUID
    reference_date: date
    curation_note: str
    divergences: list[SourceDivergence]


class RuleStep(Contract):
    """Um resultado calculado em código, com a demonstração e as fontes dos parâmetros usados."""

    label: str
    rule: str
    result_text: str
    result_date: date | None = None
    result_value: float | None = None
    computation: list[str]
    fact_keys: list[str]
    citations: list[Citation]


class RuleResult(Contract):
    rule: str
    steps: list[RuleStep]
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class VacationScheduleRequest(Contract):
    start_date: date = Field(description="Início de gozo (D)")
    holidays: list[date] = Field(
        default_factory=list, max_length=366, description="Feriados da sede; o acervo não traz o calendário"
    )
    request_registered_on: date | None = Field(default=None, description="Data de registro da solicitação")
    notice_received_on: date | None = Field(default=None, description="Data de recebimento do aviso")


class TeamAbsenceRequest(Contract):
    team_size: int = Field(ge=1, le=100000)


class UnjustifiedAbsencesRequest(Contract):
    absences: int = Field(ge=0, le=366)


class AmountRequest(Contract):
    amount: float = Field(gt=0, le=1_000_000_000)


class VacationCalculation(VacationScheduleRequest):
    rule: Literal["ferias.prazos"]


class TeamCalculation(TeamAbsenceRequest):
    rule: Literal["ferias.ausencia_simultanea"]


class AbsencesCalculation(UnjustifiedAbsencesRequest):
    rule: Literal["ferias.dias_por_faltas"]


class ReimbursementCalculation(AmountRequest):
    rule: Literal["ferias.ressarcimento"]


class ApprovalCalculation(AmountRequest):
    rule: Literal["inovacao.alcada"]


class BudgetCalculation(Contract):
    rule: Literal["inovacao.orcamento"]


class PrizeCalculation(Contract):
    rule: Literal["inovacao.pagamento_premiacao"]


CalculationRequest = Annotated[
    VacationCalculation
    | TeamCalculation
    | AbsencesCalculation
    | ReimbursementCalculation
    | ApprovalCalculation
    | BudgetCalculation
    | PrizeCalculation,
    Field(discriminator="rule"),
]


class QuestionRequest(Contract):
    topic_id: UUID
    question: str = Field(min_length=1, max_length=4000, pattern=r"\S")
    reference_date: date | None = None
    perspective: Perspective | None = None
    filters: QuestionFilters = Field(default_factory=QuestionFilters)
    calculation: CalculationRequest | None = None


class QuestionResponse(Contract):
    calculation: RuleResult | None = None
    notice: str | None = None
    mode: Literal["extractive", "generated"]
    status: Literal["supported", "partial", "insufficient", "divergent"]
    reference_date: date
    claims: list[Claim]
    passages: list[Citation]
    gaps: list[str]
    divergences: list[Divergence]
    divergence_notices: list[DivergenceNotice] = Field(
        default_factory=list, description="Divergências curadas que envolvem as fontes recuperadas"
    )
