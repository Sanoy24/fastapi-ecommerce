import asyncio
import sys

from elasticsearch import AsyncElasticsearch

from app.core.config import settings
from app.core.logger import logger

es: AsyncElasticsearch | None = None


async def get_es_client() -> AsyncElasticsearch | None:
    """
    Return the currently-connected Elasticsearch client, or None.

    This never blocks and never retries — connecting happens in
    connect_es_client_with_retries() below, run as a background task from
    app.main's lifespan rather than awaited directly. Every caller already
    treats None as "Elasticsearch unavailable" (see
    app/api/v1/routes/healthcheck.py and ElasticService, which both take
    an `AsyncElasticsearch | None`), so returning it immediately while a
    connection attempt is still in flight is consistent with that — not a
    new kind of failure to handle.
    """
    return es


async def connect_es_client_with_retries() -> AsyncElasticsearch | None:
    """
    Establish the Elasticsearch client, retrying up to 10 times, 5s apart
    (up to ~50s worst case) if it isn't immediately reachable — the common
    case right after `docker-compose up`, before Elasticsearch has
    finished its own boot.

    This function *is* what get_es_client() used to be, awaited directly
    from app.main.py's lifespan: every app startup blocked for this entire
    window whenever Elasticsearch wasn't instantly available, since
    nothing else in the app could serve a single request until lifespan
    reached `yield`. It's now meant to be run as a background task (see
    app.main.lifespan) so the app starts accepting traffic immediately
    regardless of how long Elasticsearch takes to come up — search-related
    routes just stay unavailable via get_es_client() returning None until
    this finishes.
    """
    global es

    if "pytest" in sys.modules:
        return None

    if es is not None:
        return es

    logger.info("Initializing Elasticsearch client...")
    client = AsyncElasticsearch(
        hosts=[settings.ELASTIC_URL or "http://elasticsearch:9200"],
        request_timeout=5,
        retry_on_timeout=True,
        max_retries=5,
        sniff_on_start=False,
    )

    for attempt in range(10):
        try:
            logger.info(f"Elasticsearch ping attempt {attempt + 1}/10...")
            if await client.ping():
                logger.info("Elasticsearch connected successfully")
                es = client
                return es
        except Exception as e:
            logger.warning(f"Elasticsearch ping failed: {e}")
        await asyncio.sleep(5)

    logger.error("Elasticsearch connection failed after retries")
    await client.close()
    return None


async def close_es_client():
    global es
    if es:
        await es.close()
        logger.info("Elasticsearch connection closed")
        es = None
