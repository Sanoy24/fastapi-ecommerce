from typing import Annotated

from fastapi import APIRouter, Body, Depends

from app.dependencies import get_elastic_service_dep
from app.services.elasticsearch_service import ElasticService

router = APIRouter(tags=["ELastic"])
elastic_dependency = Annotated[ElasticService, Depends(get_elastic_service_dep)]


@router.get("/health")
async def elastic_health_check(elastic_service: elastic_dependency):
    return await elastic_service.ping()


@router.post("/search")
async def search(elastic_service: elastic_dependency, query: dict = Body(...)):
    return await elastic_service.search(query)


@router.get("/suggest")
async def suggest(elastic_service: elastic_dependency, text: str):
    return await elastic_service.suggest(text=text)
