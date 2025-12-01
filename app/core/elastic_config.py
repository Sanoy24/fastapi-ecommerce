import asyncio

from elasticsearch import AsyncElasticsearch

from app.core.config import settings
from app.core.logger import logger

es: AsyncElasticsearch | None = None


async def get_es_client() -> AsyncElasticsearch:
    global es

    if es is None:
        logger.info("Initializing Elasticsearch client...")

        es = AsyncElasticsearch(
            hosts=[
                (
                    settings.ELASTIC_URL
                    if settings.ELASTIC_URL
                    else "http://elasticsearch:9200"
                )
            ],
            request_timeout=30,
            retry_on_timeout=True,
            max_retries=5,
            sniff_on_start=False,
        )

        for attempt in range(10):
            try:
                logger.info(f"Elasticsearch ping attempt {attempt+1}/10...")
                if await es.ping():
                    logger.info(" Elasticsearch connected successfully")
                    return es

            except Exception as e:
                logger.warning(f" Elasticsearch ping failed: {e}")

            await asyncio.sleep(5)

        if not await es.ping():
            logger.error(" Elasticsearch connection failed after retries")
            await es.close()
            es = None
            raise RuntimeError("Elasticsearch connection failed")

    return es


async def close_es_client():
    global es
    if es:
        await es.close()
        logger.info("Elasticsearch connection closed")
        es = None
        logger.info("Elasticsearch connection closed")
        es = None
