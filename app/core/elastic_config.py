import asyncio

from elasticsearch import AsyncElasticsearch

from app.core.logger import logger

es: AsyncElasticsearch | None = None


async def get_es_client() -> AsyncElasticsearch:
    global es

    if es is None:
        logger.info("Initializing Elasticsearch client...")

        es = AsyncElasticsearch(
            hosts=["http://localhost:9200"],
            request_timeout=30,
            retry_on_timeout=True,
            max_retries=5,
            sniff_on_start=False,
        )

        # Retry for ~15 seconds
        for attempt in range(6):
            try:
                logger.info(f"Elasticsearch ping attempt {attempt+1}/6...")
                if await es.ping():
                    logger.info(" Elasticsearch connected successfully")
                    return es

            except Exception as e:
                logger.warning(f" Elasticsearch ping failed: {e}")

            await asyncio.sleep(3)  # YOU NEED THIS

        # Final check
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
