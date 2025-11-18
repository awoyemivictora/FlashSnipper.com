import os
import aiohttp
from app.utils.bot_logger import get_logger

logger = get_logger(__name__)

WEBACY_API_URL = os.getenv("WEBACY_API_URL", "https://api.webacy.com/v1/risk")
WEBACY_TOKEN = os.getenv("WEBACY_TOKEN")

async def check_webacy_risk(mint: str) -> dict:
    try:
        headers = {"Authorization": f"Bearer {WEBACY_TOKEN}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{WEBACY_API_URL}/{mint}", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "risk_score": data.get("risk_score", 100),
                        "risk_level": data.get("risk_level", "high"),
                        "moon_potential": data.get("moon_potential", 0),
                    }
                logger.error(f"Webacy API error for {mint}: {resp.status}")
                return {"risk_score": 100, "risk_level": "high", "moon_potential": 0}
    except Exception as e:
        logger.error(f"Webacy check failed for {mint}: {e}")
        return {"risk_score": 100, "risk_level": "high", "moon_potential": 0}
    
    
    