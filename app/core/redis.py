import json
from typing import Any, Optional
import redis

from app.core.logger import logger
from app.core.config import setting


class RedisManager:
    _instance = None

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def connect(self):
        if not self.redis_client:
            self.redis_client = redis.from_url(
                setting.REDIS_URL, encoding="utf-8", decode_responses=True
            )
            logger.info(f"Connected to Redis: {self.redis_client.ping()}")

    async def close(self):
        if self.redis_client:
            self.redis_client.close()
            logger.info("Closed Redis connection")

    async def get(self, key: str) -> Any:
        if self.redis_client:
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
        return None

    async def set(self, key: str, value: Any, expire: int = 3600):
        if self.redis_client:
            await self.redis_client.set(key, json.dumps(value), ex=expire)

    async def delete(self, key: str):
        if self.redis_client:
            await self.redis_client.delete(key)

    async def delete_pattern(self, pattern: str):
        """Delete all keys matching a pattern (useful for invalidating lists)"""
        if self.redis_client:
            keys = await self.redis_client.keys(pattern)
            if keys:
                await self.redis_client.delete(*keys)
