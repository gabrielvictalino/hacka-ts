from datetime import date, datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from app.auth import current_identity, require_management
from app.contracts import DivergenceNotice, TopicDivergences
from app.db import get_engine
from app.divergencias.painel import divergence_notices, topic_divergences

router = APIRouter(tags=["divergences"])

TopicQuery = Annotated[UUID, Query(description="ID do tema")]
ReferenceQuery = Annotated[date | None, Query(description="Padrão: hoje em America/Recife")]


def _load(topic_id: UUID, reference_date: date | None, build):
    reference = reference_date or datetime.now(ZoneInfo("America/Recife")).date()
    with get_engine().connect() as connection:
        if not connection.execute(text("SELECT 1 FROM topics WHERE id=:id"), {"id": topic_id}).scalar():
            raise HTTPException(404, "Tema não encontrado.")
        return build(connection, topic_id, reference)


@router.get(
    "/api/divergencias",
    response_model=TopicDivergences,
    dependencies=[Depends(require_management)],
    description="Detalhes das divergências curadas manualmente: cenário, condições, passagens, precedência "
    "declarada e dados faltantes. Reservado à Gestão do acervo.",
    responses={403: {"description": "Operação reservada à Gestão"}, 404: {"description": "Tema não encontrado"}},
)
def divergences(topic_id: TopicQuery, reference_date: ReferenceQuery = None):
    return _load(topic_id, reference_date, topic_divergences)


@router.get(
    "/api/divergencias/avisos",
    response_model=list[DivergenceNotice],
    dependencies=[Depends(current_identity)],
    description="Aviso curto da Consulta para as divergências aplicáveis na data, sem os detalhes da Gestão.",
    responses={404: {"description": "Tema não encontrado"}},
)
def notices(topic_id: TopicQuery, reference_date: ReferenceQuery = None):
    return _load(topic_id, reference_date, divergence_notices)
