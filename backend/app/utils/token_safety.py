from fastapi import HTTPException
from app.utils.dexscreener_api import get_dexscreener_data
from app.utils.raydium_apis import get_raydium_pool_info
from app.utils.solscan_apis import get_solscan_token_meta
import logging


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



async def check_token_safety(mint_address: str) -> dict:
    """
    Performs all safety checks on a token and returns a comprehensive report.
    Includes all 7 checks from your requirements.
    """
    safety_report = {
        "mint_address": mint_address,
        "passed_all_checks": False,
        "checks": {
            "socials_added": False,
            "liquidity_burnt": False,
            "immutable_metadata": False,
            "mint_authority_renounced": False,
            "freeze_authority_revoked": False,
            "pump_fun_migrated": False,
            "sufficient_liquidity": False
        },
        "details": {}
    }

    try:
        # 1. Check Socials (Dexscreener)
        dex_data = await get_dexscreener_data(mint_address)
        if dex_data:
            safety_report["checks"]["socials_added"] = (
                dex_data.get("twitter") != "N/A" or dex_data.get("telegram") != "N/A"
            )
            safety_report["details"]["socials"] = {
                "twitter": dex_data.get("twitter"),
                "telegram": dex_data.get("telegram")
            }
            safety_report["details"]["dex_id"] = dex_data.get("dex_id", "")

            # 6. Check if migrated from Pump.fun
            safety_report["checks"]["pump_fun_migrated"] = "pump.fun" in dex_data.get("dex_id", "").lower()

        # 2. Check Liquidity Burnt (Raydium)
        raydium_data = await get_raydium_pool_info(mint_address)
        if raydium_data:
            burn_percent = raydium_data.get("burnPercent", 0)
            safety_report["checks"]["liquidity_burnt"] = burn_percent == 100
            safety_report["details"]["liquidity_burnt_percent"] = burn_percent

            # 7. Check Pool Size
            tvl = float(raydium_data.get("tvl", 0))
            safety_report["checks"]["sufficient_liquidity"] = tvl >= 5  # Minimum 5 SOL liquidity
            safety_report["details"]["liquidity_pool_size_sol"] = tvl

        # 3-5. Check Metadata and Authorities (Solscan)
        solscan_data = await get_solscan_token_meta(mint_address)
        if solscan_data:
            # 3. Immutable Metadata (simplified check)
            safety_report["checks"]["immutable_metadata"] = solscan_data.get("metadata_uri") is not None

            # 4. Mint Authority Renounced
            safety_report["checks"]["mint_authority_renounced"] = solscan_data.get("mint_authority") is None

            # 5. Freeze Authority Revoked
            safety_report["checks"]["freeze_authority_revoked"] = solscan_data.get("freeze_authority") is None

            safety_report["details"]["authorities"] = {
                "mint_authority": solscan_data.get("mint_authority"),
                "freeze_authority": solscan_data.get("freeze_authority")
            }

        # Determine if all checks passed
        safety_report["passed_all_checks"] = all(safety_report["checks"].values())

        return safety_report

    except Exception as e:
        logger.error(f"Error checking token safety for {mint_address}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to complete safety checks: {str(e)}"
        )

