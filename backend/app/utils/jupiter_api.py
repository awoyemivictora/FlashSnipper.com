# jupiter_api.py
import asyncio
import logging
from typing import Optional, Dict, Any
import httpx

# --------------------------------------------------------------
# Logging setup
# --------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

JUPITER_SEARCH_URL = "https://lite-api.jup.ag/tokens/v2/search"


def safe_float(value, default: float = 0.0) -> float:
    """Safely convert to float, handles None, "", "null", etc."""
    try:
        if value in (None, "", "null", "N/A"):
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default: int = 0) -> int:
    try:
        if value in (None, "", "null", "N/A"):
            return default
        return int(value)
    except (ValueError, TypeError):
        return default


async def get_jupiter_token_data(mint_address: str) -> Optional[Dict[str, Any]]:
    """
    Fetch FULL token metadata from Jupiter Lite API v2 using mint address.
    Extracts 100% of the fields from the real response (including nested stats, audit, etc.)
    """
    params = {"query": mint_address}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(JUPITER_SEARCH_URL, params=params)
            response.raise_for_status()
            results = response.json()

        if not results or not isinstance(results, list):
            logger.info(f"Jupiter: Empty or invalid response for {mint_address[:8]}")
            return None

        # Find exact mint match
        token = None
        for t in results:
            if t.get("id", "").lower() == mint_address.lower():
                token = t
                break

        if not token:
            logger.info(f"Jupiter: Token {mint_address[:8]} not found in results")
            return None

        # === Extract EVERYTHING ===
        audit = token.get("audit", {})
        first_pool = token.get("firstPool", {})
        stats1h = token.get("stats1h", {})
        stats6h = token.get("stats6h", {})
        stats24h = token.get("stats24h", {})

        return {
            # Core token info
            "mint_address": token.get("id"),
            "name": token.get("name", "Unknown"),
            "symbol": token.get("symbol", "UNKNOWN"),
            "icon": token.get("icon") or f"https://dd.dexscreener.com/ds-logo/solana/{mint_address}.png",
            "decimals": safe_int(token.get("decimals")),

            # Socials (direct fields
            "twitter": token.get("twitter") or "N/A",
            "telegram": token.get("telegram") or "N/A",
            "website": token.get("website") or "N/A",

            # Dev & supply
            "dev": token.get("dev"),
            "circulating_supply": safe_float(token.get("circSupply")),
            "total_supply": safe_float(token.get("totalSupply")),
            "token_program": token.get("tokenProgram"),

            # Pool & launch
            "first_pool_id": first_pool.get("id"),
            "first_pool_created_at": first_pool.get("createdAt"),
            "created_at": token.get("createdAt"),  # Token creation time
            "updated_at": token.get("updatedAt"),

            # Holders & economics
            "holder_count": safe_int(token.get("holderCount")),
            "fdv": safe_float(token.get("fdv")),
            "market_cap": safe_float(token.get("mcap")),
            "usd_price": safe_float(token.get("usdPrice")),
            "liquidity_usd": safe_float(token.get("liquidity")),

            # Audit / Safety
            "is_suspicious": bool(audit.get("isSus")),
            "mint_authority_disabled": bool(audit.get("mintAuthorityDisabled")),
            "freeze_authority_disabled": bool(audit.get("freezeAuthorityDisabled")),
            "top_holders_percentage": safe_float(audit.get("topHoldersPercentage")),
            "blockaid_rugpull": bool(audit.get("blockaidRugpull")),
            "blockaid_honeypot": bool(audit.get("blockaidHoneypot")),

            # Organic score
            "organic_score": safe_int(token.get("organicScore")),
            "organic_score_label": token.get("organicScoreLabel", "unknown"),

            # Tags
            "tags": token.get("tags", []),

            # Stats 1h
            "price_change_1h": safe_float(stats1h.get("priceChange")),
            "holder_change_1h": safe_float(stats1h.get("holderChange")),
            "volume_change_1h": safe_float(stats1h.get("volumeChange")),

            # Stats 6h
            "price_change_6h": safe_float(stats6h.get("priceChange")),
            "holder_change_6h": safe_float(stats6h.get("holderChange")),
            "volume_change_6h": safe_float(stats6h.get("volumeChange")),

            # Stats 24h
            "price_change_24h": safe_float(stats24h.get("priceChange")),
            "holder_change_24h": safe_float(stats24h.get("holderChange")),
            "liquidity_change_24h": safe_float(stats24h.get("liquidityChange")),
            "volume_change_24h": safe_float(stats24h.get("volumeChange")),
            "sell_volume_24h": safe_float(stats24h.get("sellVolume")),
            "num_sells_24h": safe_int(stats24h.get("numSells")),
            "num_traders_24h": safe_int(stats24h.get("numTraders")),

            # Misc
            "price_block_id": token.get("priceBlockId"),
            "jupiter_url": f"https://jup.ag/token/{mint_address}",
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"Jupiter HTTP {e.response.status_code} for {mint_address[:8]}")
        return None
    except Exception as e:
        logger.error(f"Jupiter fetch error {mint_address[:8]}: {e}")
        return None


# ===================================================================
# Smart Jupiter Fetch with Retry (Same style as your DexScreener)
# ===================================================================
async def fetch_jupiter_with_retry(mint: str, max_attempts: int = 10) -> dict:
    """
    Retries until Jupiter indexes the token (they're usually 10–60s behind new launches)
    Same logic you use for DexScreener.
    """
    for attempt in range(max_attempts):
        data = await get_jupiter_token_data(mint)

        if data and data.get("name") and data["name"] != "Unknown":
            price = data["usd_price"]
            mc = data.get("market_cap") or data.get("fdv") or 0
            logger.info(
                f"Jupiter READY → {mint[:8]} | {data['symbol']} | ${price:.10f} | "
                f"MC: ${mc:,.0f} | Holders: {data['holder_count']} | Attempt {attempt + 1}"
            )
            return data

        delay = min(7 + (attempt ** 2) * 8, 180)  # 7s, 39s, 87s, 151s, 180s...
        logger.info(f"Jupiter not ready {mint[:8]} → waiting {delay}s (attempt {attempt + 1})")
        await asyncio.sleep(delay)

    logger.warning(f"Jupiter failed permanently for {mint[:8]} after {max_attempts} attempts")
    return {}


#===================================================================
# TEST BLOCK — just run: python jupiter_api.py
# ===================================================================
if __name__ == "__main__":
    TEST_MINT = "CzHc1ugMNhim5JCJC8ebbp4k14jfrbZx1HNcMyEppump"  # ← your token

    async def test():
        logger.info(f"Testing Jupiter API with mint: {TEST_MINT}")
        data = await fetch_jupiter_with_retry(TEST_MINT, max_attempts=12)

        if data:
            logger.info("SUCCESS! Full metadata fetched:")
            for key, value in data.items():
                # Pretty print long values
                if isinstance(value, (list, dict)):
                    logger.info(f"  {key}: {value}")
                else:
                    logger.info(f"  {key}: {value}")
        else:
            logger.error("Failed to get any data after retries")

    asyncio.run(test())
    

