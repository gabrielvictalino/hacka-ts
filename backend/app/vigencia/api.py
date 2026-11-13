from datetime import date, datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from app.auth import current_identity
from app.contracts import TopicValidity
from app.db import get_engine
from app.vigencia.painel import topic_validity

router = APIRouter(tags=["validity"])


@router.get("/vigencia", response_model=TopicValidity, dependencies=[Depends(current_identity)])
@router.get(
    "/api/vigencia",
    response_model=TopicValidity,
    dependencies=[Depends(current_identity)],
    description="Situação temporal, camada, vínculos, precedência declarada e mudanças entre versões do tema, "
    "com as fontes de cada informação.",
    responses={404: {"description": "Tema não encontrado"}},
)
def validity(
    topic_id: Annotated[UUID, Query(description="ID do tema")],
    reference_date: Annotated[date | None, Query(description="Padrão: hoje em America/Recife")] = None,
):
    reference = reference_date or datetime.now(ZoneInfo("America/Recife")).date()
    with get_engine().connect() as connection:
        if not connection.execute(text("SELECT 1 FROM topics WHERE id=:id"), {"id": topic_id}).scalar():
            raise HTTPException(404, "Tema não encontrado.")
        return topic_validity(connection, topic_id, reference)
