from typing import Dict, Optional
import httpx
import logging
import os
from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger(__name__)


SOLSCAN_API_KEY = os.getenv("SOLSCAN_API")



async def get_top_holders_info(mint_address: str, num_top_holders: int = 10) -> float:
    """
    Fetches top holders data for a given mint address using the Solscan Pro API.
    Calculates the combined percentage held by the top 'num_top_holders'.
    
    Args:
        mint_address (str): The token's mint address on the Solana blockchain.
        num_top_holders (int): The number of top holders to consider for the sum.
        
    Returns:
        float: The percentage of total supply held by the top 'num_top_holders'.
        Returns 0.0 if data cannot be fetched or processed.
    """
    if not SOLSCAN_API_KEY:
        logger.error("Solcan API key is not set. Please set SOLSCAN_API_KEY.")
        return 0.0
    
    url = f"https://pro-api.solscan.io/v2.0/token/holders"
    headers = {"token": SOLSCAN_API_KEY}
    params = {
        "address": mint_address,
        "page": 1,
        "page_size": num_top_holders    # Request enough to cover the top N holders
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()     # Raise an exception for HTTP errors
            data = response.json()
            
        if data.get("success") and data.get("data") and data["data"].get("items"):
            holders = data["data"]["items"]
            
            if not holders:
                logger.info(f"No holders found for {mint_address}.")
                return 0.0
            
            total_supply_calculated = 0
            top_holders_sum_amount = 0
            
            # It's more reliable to use the 'percentage' directly if available.
            # or calculate total supply from the first holder's amount and percentage.
            # Let's use the 'percentage' provided by Solscan directly for the top N.
            
            top_n_percentage_sum = 0.0
            for i, holder in enumerate(holders):
                if i < num_top_holders:     # Ensure we only sum up to num_top_holders
                    top_n_percentage_sum += holder.get("percentage", 0.0)
                    
            return top_n_percentage_sum
        
        else:
            logger.warning(f"Solscan API returned an error or no data for {mint_address}: {data}")
            return 0.0
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching top holders for {mint_address}: {e.response.status_code} - {e.response.text}")
        return 0.0
    except httpx.RequestError as e:
        logger.error(f"Network error fetching top holders for {mint_address}: {e}")
        return 0.0
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching top holders for {mint_address}: {e}")
        return 0.0
    
    
    
# Example usage (you would call this from your main logic)
# async def main():
#     # Replace with a real token mint address
#     test_mint_address = "JCK1kBxZLhvXVeozAkNbdTCjWmWHaTDqu9UDPibepump"  # USDC
#     top_10_holders_percentage = await get_top_holders_info(test_mint_address, num_top_holders=10)
#     print(f"Percentage held by top 10 holders for {test_mint_address}: {top_10_holders_percentage:.2f}%")
    
    
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(main())
    
    
    




async def get_solscan_token_meta(mint_address: str) -> Optional[Dict]:
    """
    Fetches token metadata from Solscan Pro API v2.0.
    Requires a Solscan Pro API key.
    """
    if not SOLSCAN_API_KEY or SOLSCAN_API_KEY == "YOUR_SOLSCAN_PRO_API_KEY":
        logger.error("Solscan API key is not set. Please set SOLSCAN_API_KEY.")
        return None

    try:
        url = "https://pro-api.solscan.io/v2.0/token/meta"
        headers = {"token": SOLSCAN_API_KEY} # Use 'token' header for Solscan Pro API Key
        params = {"address": mint_address} # Query param for token address

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("success") and data.get("data"):
                token_meta = data["data"]
                # Solscan Pro API provides mint_authority and freeze_authority directly
                # If they are null, it means they are revoked/not set.
                return {
                    "address": token_meta.get("address"),
                    "name": token_meta.get("name"),
                    "symbol": token_meta.get("symbol"),
                    "icon": token_meta.get("icon"),
                    "decimals": token_meta.get("decimals"),
                    "holder": token_meta.get("holder"),
                    "creator": token_meta.get("creator"),
                    "create_tx": token_meta.get("create_tx"),
                    "created_time": token_meta.get("created_time"),
                    "metadata": token_meta.get("metadata"), # This will return the nested metadata object
                    "metadata_uri": token_meta.get("metadata_uri"),
                    "mint_authority": token_meta.get("mint_authority"),
                    "freeze_authority": token_meta.get("freeze_authority"),
                    "supply": token_meta.get("supply"),
                    "price": token_meta.get("price"),
                    "volume_24h": token_meta.get("volume_24h"),
                    "market_cap": token_meta.get("market_cap"),
                    "market_cap_rank": token_meta.get("market_cap_rank"),
                    "price_change_24h": token_meta.get("price_change_24h"),
                    "total_dex_vol_24h": token_meta.get("total_dex_vol_24h"),
                    "dex_vol_change_24h": token_meta.get("dex_vol_change_24h"),
                    "is_mutable": token_meta.get("mutable", True) # Solscan response shows 'mutable'. Assume True if not present.
                }
            logger.warning(f"Solscan API returned an error or no data for token meta {mint_address}: {data}")
            return None
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching Solscan token meta for {mint_address}: {e.response.status_code} - {e.response.text}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Network error fetching Solscan token meta for {mint_address}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching Solscan token meta for {mint_address}: {e}")
        return None



# Example usage (for testing)
# async def main():
#     # --- Solscan Token Meta Test ---
#     test_token_mint_address = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN" 
#     print(f"\n--- Fetching Solscan Token Meta for: {test_token_mint_address} ---")
#     solscan_meta = await get_solscan_token_meta(test_token_mint_address)
#     if solscan_meta:
#         import json
#         print(json.dumps(solscan_meta, indent=2))
#     else:
#         print(f"Failed to fetch Solscan token meta for {test_token_mint_address}")

# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(main())