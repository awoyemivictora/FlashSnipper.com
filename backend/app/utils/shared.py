import json
import logging
from datetime import datetime
from typing import Optional
import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Initialize Redis client
redis_client = redis.from_url("redis://localhost:6379", decode_responses=True)

# Bot state management
async def save_bot_state(wallet_address: str, is_running: bool, settings: dict = None):
    """Save bot state to Redis for persistence"""
    state = {
        "is_running": is_running,
        "last_heartbeat": datetime.utcnow().isoformat(),
        "settings": settings or {}
    }
    await redis_client.setex(f"bot_state:{wallet_address}", 86400, json.dumps(state))  # 24h TTL

async def load_bot_state(wallet_address: str) -> Optional[dict]:
    """Load bot state from Redis"""
    state_data = await redis_client.get(f"bot_state:{wallet_address}")
    if state_data:
        return json.loads(state_data)
    return None


