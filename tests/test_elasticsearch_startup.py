"""
Tests for Elasticsearch's startup connection no longer blocking the app
(app/main.py lifespan, app/core/elastic_config.py).

connect_es_client_with_retries() retries up to 10 times, 5 seconds apart —
up to ~50s worst case — when Elasticsearch isn't immediately reachable,
which is the normal case for the first several seconds after
`docker-compose up` while Elasticsearch is still booting. This used to be
awaited directly inside lifespan(), so the whole app — every route, not
just search — couldn't serve a single request until it finished. It's now
kicked off as a background task instead, the same pattern already used for
the reservation-cleanup loop in the same function.

connect_es_client_with_retries() itself returns None immediately when
"pytest" in sys.modules (unchanged from before), so these tests patch
app.main.connect_es_client_with_retries directly to simulate a slow/live
connection attempt rather than trying to exercise the real one.
"""
import asyncio
import time
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI

import app.core.elastic_config as elastic_config
from app.main import lifespan


class TestLifespanDoesNotBlockOnElasticsearch:
    async def test_lifespan_becomes_ready_quickly_even_when_es_is_slow(self):
        app = FastAPI()

        async def slow_connect():
            await asyncio.sleep(3)
            return None

        with patch("app.main.connect_es_client_with_retries", slow_connect):
            started = time.monotonic()
            async with lifespan(app):
                elapsed = time.monotonic() - started
                assert elapsed < 1, (
                    f"lifespan took {elapsed:.2f}s to become ready while the ES "
                    f"connection was still in flight — startup is blocking on it again"
                )

    async def test_lifespan_shutdown_does_not_hang_waiting_for_es(self):
        """Exiting lifespan cancels the background ES task rather than
        waiting for a still-in-flight (or permanently stuck) connection
        attempt to finish on its own."""
        app = FastAPI()

        async def never_finishes():
            await asyncio.sleep(3600)
            return None

        with patch("app.main.connect_es_client_with_retries", never_finishes):
            started = time.monotonic()
            async with lifespan(app):
                pass
            elapsed = time.monotonic() - started

        assert elapsed < 2, f"lifespan shutdown took {elapsed:.2f}s — it should cancel the ES task, not wait for it"


class TestElasticsearchConnectsInTheBackground:
    def teardown_method(self):
        # elastic_config.es is process-global — reset it so this test
        # doesn't leak a fake client into any other test in the suite.
        elastic_config.es = None

    async def test_get_es_client_reflects_the_connection_once_it_completes(self):
        app = FastAPI()
        # close_es_client() (unconditionally called on lifespan shutdown)
        # awaits fake_client.close() — a plain sentinel object won't do.
        fake_client = AsyncMock()

        async def fake_connect():
            await asyncio.sleep(0.2)
            elastic_config.es = fake_client
            return fake_client

        with patch("app.main.connect_es_client_with_retries", fake_connect), \
             patch("app.main.create_product_index", new_callable=AsyncMock), \
             patch("app.main.bulk_index_products", new_callable=AsyncMock):
            async with lifespan(app):
                # Not connected yet — the background task is still sleeping.
                assert await elastic_config.get_es_client() is None

                # ...but it completes shortly after, without anyone having
                # blocked waiting for it.
                deadline = time.monotonic() + 2
                while await elastic_config.get_es_client() is None and time.monotonic() < deadline:
                    await asyncio.sleep(0.05)

                assert await elastic_config.get_es_client() is fake_client

    async def test_index_warming_runs_after_a_successful_connection(self):
        app = FastAPI()
        fake_client = object()

        async def fake_connect():
            return fake_client

        with patch("app.main.connect_es_client_with_retries", fake_connect), \
             patch("app.main.create_product_index", new_callable=AsyncMock) as mock_create_index, \
             patch("app.main.bulk_index_products", new_callable=AsyncMock) as mock_bulk_index:
            async with lifespan(app):
                deadline = time.monotonic() + 2
                while not mock_create_index.called and time.monotonic() < deadline:
                    await asyncio.sleep(0.05)

            mock_create_index.assert_awaited_once_with(fake_client)
            mock_bulk_index.assert_awaited_once_with(fake_client)

    async def test_index_warming_is_skipped_when_connection_never_succeeds(self):
        app = FastAPI()

        async def failing_connect():
            return None

        with patch("app.main.connect_es_client_with_retries", failing_connect), \
             patch("app.main.create_product_index", new_callable=AsyncMock) as mock_create_index, \
             patch("app.main.bulk_index_products", new_callable=AsyncMock) as mock_bulk_index:
            async with lifespan(app):
                await asyncio.sleep(0.1)

            mock_create_index.assert_not_awaited()
            mock_bulk_index.assert_not_awaited()
