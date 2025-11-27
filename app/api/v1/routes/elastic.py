from typing import Annotated

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Body, Depends

from app.dependencies import get_elastic_service_dep

router = APIRouter(tags=["ELastic"])
elastic_dependency = Annotated[AsyncElasticsearch, Depends(get_elastic_service_dep)]


@router.get("/health")
async def elastic_health_check(elastic_service: elastic_dependency):
    return await elastic_service.ping()


@router.post("/search")
async def search(elastic_service: elastic_dependency, query: dict = Body(...)):
    return await elastic_service.search_elastic()
