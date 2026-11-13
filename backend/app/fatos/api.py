from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.auth import current_identity, require_management
from app.contracts import CuratedFact, CurationReport, Perspective
from app.db import get_engine
from app.fatos.curadoria import publish_catalog
from app.fatos.repositorio import list_facts

router = APIRouter(tags=["facts"])


@router.get("/fatos", response_model=list[CuratedFact], dependencies=[Depends(current_identity)])
@router.get(
    "/api/fatos",
    response_model=list[CuratedFact],
    dependencies=[Depends(current_identity)],
    description="Fatos curados para perspectivas, filtros e visuais. Obrigações e Riscos ainda não têm curadoria.",
)
def facts(
    categoria: Annotated[Perspective | None, Query(description="deadline = Prazos, value = Valores")] = None,
    assunto: Annotated[UUID | None, Query(description="ID do tema")] = None,
    area: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
):
    with get_engine().connect() as connection:
        return list_facts(connection, category=categoria, topic_id=assunto, area=area)


@router.post(
    "/api/fatos/curadoria",
    response_model=CurationReport,
    dependencies=[Depends(require_management)],
    description="Publica o catálogo revisado para as edições já ingeridas; fatos sem fonte disponível ficam pendentes.",
)
def publish():
    with get_engine().begin() as connection:
        return publish_catalog(connection)
