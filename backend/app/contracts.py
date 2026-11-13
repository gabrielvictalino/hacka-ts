"""Fonte dos contratos Python, OpenAPI e tipos TypeScript gerados."""

from datetime import date
from enum import StrEnum
from typing import Literal
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


class QuestionRequest(Contract):
    topic_id: UUID
    question: str = Field(min_length=1, max_length=4000)
    reference_date: date | None = None
    perspective: Perspective | None = None
    filters: QuestionFilters = Field(default_factory=QuestionFilters)


class Claim(Contract):
    text: str
    citations: list[Citation] = Field(min_length=1)


class Divergence(Contract):
    classification: Literal["confirmed", "possible"]
    reasoning: str
    missing_information: list[str]
    citations: list[Citation] = Field(min_length=2)


class QuestionResponse(Contract):
    mode: Literal["extractive", "generated"]
    status: Literal["supported", "partial", "insufficient", "divergent"]
    reference_date: date
    claims: list[Claim]
    passages: list[Citation]
    gaps: list[str]
    divergences: list[Divergence]
