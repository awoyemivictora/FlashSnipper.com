# app/middleware/rate_limiter.py
import time
from typing import Callable
from fastapi import Request, HTTPException, Depends
from app.config import settings
import redis.asyncio as redis

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=6379,
    db=0,
    decode_responses=True
)

async def rate_limit(request: Request, calls: int = 10, per_seconds: int = 60):
    key = f"rate_limit:{request.client.host}:{request.url.path}"
    current = await redis_client.get(key)
    
    if current is None:
        await redis_client.setex(key, per_seconds, 1)
    elif int(current) >= calls:
        raise HTTPException(status_code=429, detail="Too many requests")
    else:
        await redis_client.incr(key)

    return True


def rate_limited(calls: int = 10, per_seconds: int = 60) -> Callable:
    """
    Factory function to create a rate limit dependency with custom limits
    Usage: Depends(rate_limited(calls=5, per_seconds=60))
    """
    async def dependency(request: Request):
        await rate_limit(request, calls=calls, per_seconds=per_seconds)
        return True
    return Depends(dependency)

