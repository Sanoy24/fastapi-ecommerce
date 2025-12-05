from typing import Any, Dict

from elasticsearch import (
    AsyncElasticsearch,
    AuthenticationException,
    ConnectionError,
    NotFoundError,
    RequestError,
)
from fastapi import HTTPException, status

from app.core.logger import logger


class ElasticService:
    INDEX = "products"

    def __init__(self, es: AsyncElasticsearch):
        self.es = es

    async def ping(self):
        try:
            info = await self.es.info()
            health = await self.es.cluster.health()
            return {
                "status": "healthy",
                "cluster_name": info["cluster_name"],
                "version": info["version"]["number"],
                "cluster_status": health["status"],
                "node_count": health["number_of_nodes"],
                "active_shards_percent": health["active_shards_percent_as_number"],
            }
        except (ConnectionError, AuthenticationException) as e:
            logger.error(f"Elasticsearch unreachable: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="elasticseach unreachable",
            )
        except Exception as e:
            logger.exception("Unexpected error during Elasticsearch ping")
            raise HTTPException(status_code=500, detail="Internal Elasticsearch error")

    async def search(
        self,
        query: Dict[str, Any],
        index: str = INDEX,
        size: int = 20,
        from_: int = 0,
        highlight: bool = True,
    ):
        if size > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum size is 100"
            )
        if highlight and "highlight" not in query:
            query["highlight"] = {
                "fields": {
                    "name": {"pre_tags": ["<em>"], "post_tags": ["</em>"]},
                    "description": {"pre_tags": ["<em>"], "post_tags": ["</em>"]},
                }
            }
        try:
            result = await self.es.search(
                index=index,
                body=query,
                size=size,
                from_=from_,
                rest_total_hits_as_int=True,
            )

            hits = result["hits"]["hits"]
            return {
                "total": result["hits"]["total"],
                "took_ms": result["took"],
                "results": [
                    {
                        "id": hit["_id"],
                        "score": hit["_score"],
                        "data": hit["_source"],
                        "highlight": hit.get("highlight", {}),
                    }
                    for hit in hits
                ],
            }

        except NotFoundError:
            raise HTTPException(status_code=404, detail=f"Index '{index}' not found")
        except RequestError as e:

            logger.warning(f"Bad search query: {query} → {e}")
            error_msg = e.info.get("error", {}).get("reason", str(e))
            raise HTTPException(
                status_code=400, detail=f"Invalid search query: {error_msg}"
            )
        except ConnectionError as e:
            logger.error(f"Elasticsearch connection failed during search: {e}")
            raise HTTPException(
                status_code=503, detail="Search temporarily unavailable"
            )
        except Exception as e:
            logger.exception("Unexpected error in search")
            raise HTTPException(status_code=500, detail="Search failed")

    async def suggest(
        self, text: str, size: int = 10, category: str | None = None
    ) -> list[str]:

        if not text or len(text.strip()) < 2:
            return []

        body = {
            "suggest": {
                "product-suggest": {
                    "prefix": text.strip(),
                    "completion": {
                        "field": "suggest",
                        "size": size,
                        "fuzzy": {"fuzziness": "AUTO"},
                        "contexts": {"category": [category] if category else ["all"]},
                    },
                }
            }
        }

        try:
            result = await self.es.search(index=self.INDEX, body=body)
            options = result["suggest"]["product-suggest"][0]["options"]
            return [opt["text"] for opt in options]
        except Exception as e:
            logger.warning(f"Completion suggest failed: {e}")
            return []
