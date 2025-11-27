from elasticsearch import AsyncElasticsearch
from fastapi import HTTPException


class ElasticService:
    def __init__(self, es: AsyncElasticsearch):
        self.es = es

    async def ping(self):
        try:
            health = await self.es.cluster.health()
            return {
                "status": "success",
                "message": "connected to elastic search",
                "cluster_status": health["status"],
                "number_of_nodes": health["number_of_nodes"],
                "active_shards": health["active_shards"],
            }
        except Exception as e:
            status_code = getattr(e, "status_code", 500)

            raise HTTPException(
                status_code=status_code,
                detail=f"Error connecting to Elasticsearch: {str(e)}",
            )

    async def search_elastic(self, query: dict):
        try:
            result = await self.es.search(index="products", body=query)

            return result
        except Exception as e:
            status_code = getattr(e, "status_code", 500)

            raise HTTPException(status_code=status_code, detail=str(e))
