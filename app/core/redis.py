# app/core/redis.py
import json
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

import redis.asyncio as redis
from app.core.logger import logger
from app.core.config import settings


class RedisClient:
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._pool: Optional[redis.ConnectionPool] = None

    async def connect(self) -> None:
        if self._client is not None:
            return

        self._pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
            retry_on_timeout=True,
        )
        self._client = redis.Redis(connection_pool=self._pool)

        try:
            await self._client.ping()
            logger.info("Redis connected successfully")
        except redis.RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            if self._pool:
                await self._pool.disconnect()
            self._client = None
            self._pool = None
            logger.info("Redis connection closed")

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError(
                "Redis client not initialized. Call connect() first or use lifespan."
            )
        return self._client

    async def get_json(self, key: str) -> Any:
        value = await self.client.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.warning(f"Failed to decode JSON for key: {key}")
            return value

    async def set_json(self, key: str, value: Any, ex: Optional[int] = 3600) -> None:
        await self.client.set(key, json.dumps(value, ensure_ascii=False), ex=ex)

    async def delete(self, key: str) -> int:
        return await self.client.delete(key)

    async def delete_pattern(self, pattern: str) -> int:
        keys = await self.client.keys(pattern)
        if not keys:
            return 0
        return await self.client.delete(*keys)


redis_client = RedisClient()
