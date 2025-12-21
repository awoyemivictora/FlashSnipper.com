# app/utils/redis_client.py
import redis.asyncio as redis
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Global Redis client instance
_redis_client = None

def get_redis_client() -> redis.Redis:
    """Get or create a single Redis client instance for the entire app"""
    global _redis_client
    
    if _redis_client is None:
        # Use settings from your config
        redis_host = getattr(settings, "REDIS_HOST", "localhost")
        redis_port = getattr(settings, "REDIS_PORT", 6379)
        redis_db = getattr(settings, "REDIS_DB", 0)
        
        _redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True,
            max_connections=50,
            socket_keepalive=True
        )
        logger.info(f"✅ Redis client initialized: {redis_host}:{redis_port}")
    
    return _redis_client

async def close_redis_client():
    """Close the Redis connection"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis client closed")
        
        
        
        