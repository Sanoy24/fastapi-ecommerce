from fastapi import Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
import json
import hashlib
from app.core.redis import redis_client
from typing import Optional, Callable
from functools import wraps

async def check_idempotency(
    request: Request,
    idempotency_key: str = Header(None, alias="Idempotency-Key")
):
    """
    Dependency to check if an Idempotency-Key exists in the header.
    If it does, it checks Redis for a cached response.
    If a cached response exists, it raises an HTTPException that a custom exception handler will catch
    to return the cached JSONResponse.
    If not, it just returns the key so the route can cache the result later.
    """
    if not idempotency_key:
        return None
        
    # Create a unique hash based on user (if any), path, and idempotency key
    # to prevent cross-user key collisions
    auth_header = request.headers.get("Authorization", "")
    base_string = f"{auth_header}:{request.url.path}:{idempotency_key}"
    key_hash = hashlib.sha256(base_string.encode()).hexdigest()
    redis_key = f"idempotency:{key_hash}"
    
    cached_response = await redis_client.get(redis_key)
    if cached_response:
        data = json.loads(cached_response)
        # We use a custom exception to short-circuit the route and return the cached response
        raise IdempotentResponseException(
            status_code=data.get("status_code", 200),
            content=data.get("content", {})
        )
        
    return redis_key


class IdempotentResponseException(Exception):
    def __init__(self, status_code: int, content: dict):
        self.status_code = status_code
        self.content = content


async def cache_idempotent_response(redis_key: str, response_data: dict, status_code: int = 200, expire_secs: int = 86400):
    """Cache the successful response in Redis for the given key."""
    if not redis_key:
        return
        
    cache_data = {
        "status_code": status_code,
        "content": response_data
    }
    await redis_client.setex(redis_key, expire_secs, json.dumps(cache_data))
