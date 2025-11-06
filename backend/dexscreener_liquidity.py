#------------------- RAW DATA FETCHED FOR A MINT ADDRESS ON DEXSCREENER ------------
# import requests

# def get_dexscreener_liquidity(mint_address: str) -> float:
#     """
#     Calls the Dexscreener API to fetch liquidity data for a given token on Solana.
    
#     Args:
#         mint_address (str): The token mint address.
        
#     Returns:
#         float: The liquidity in USD if available; otherwise, 0.0.
#     """
#     # Build the URL for Solana and the provided mint address.
#     url = f"https://api.dexscreener.com/token-pairs/v1/solana/{mint_address}"
#     try:
#         response = requests.get(url)
#         response.raise_for_status()
#         data = response.json()
#         print(data)
#         # Dexscreener returns an array of pool objects.
#         # We'll iterate over the list and pick the highest liquidity (or just the first one if that's acceptable).
#         pools = data if isinstance(data, list) else data.get("data", [])
#         if pools:
#             # For simplicity, we'll take the first pool's liquidity in USD.
#             liquidity_info = pools[0].get("liquidity", {})
#             liquidity_usd = liquidity_info.get("usd", 0.0)
#             return float(liquidity_usd)
#         else:
#             return 0.0
#     except Exception as e:
#         print(f"Error fetching Dexscreener liquidity for {mint_address}: {e}")
#         return 0.0

# # Example usage:
# if __name__ == "__main__":
#     test_mint = "2sCUCJdVkmyXp4dT8sFaA9LKgSMK4yDPi9zLHiwXpump"  # Example token mint
#     liquidity = get_dexscreener_liquidity(test_mint)
#     print(f"Liquidity for {test_mint} on Dexscreener: {liquidity}")











#----------------------- FILTERED RAW DATA FETCHED FOR A MINT ADDRESS ON DEXSCREENER --------

import requests

def get_dexscreener_data(mint_address: str) -> dict:
    """
    Fetches pool data from Dexscreener for the given token mint on Solana.
    Extracts the following fields:
      - dexscreener_url: The URL for the pool on Dexscreener.
      - pair_address: The pool's pair address.
      - price_native: The native price as a string.
      - price_usd: The USD price as a string.
      - liquidity: The liquidity in USD.
      - market_cap: The market capitalization.
      - pair_created_at: The timestamp (epoch) when the pair was created.
      - websites: Concatenated website URLs (if any).
      - twitter: The Twitter URL from socials.
      - telegram: The Telegram URL from socials.
    Returns a dict with these fields (or default values if not found).
    """
    url = f"https://api.dexscreener.com/token-pairs/v1/solana/{mint_address}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        # Dexscreener returns an array of pool objects.
        if not data or not isinstance(data, list) or len(data) == 0:
            return {}
        # We'll use the first pool for our data.
        pool = data[0]

        # Extract basic fields.
        dexscreener_url = pool.get("url", "")
        pair_address = pool.get("pairAddress", "")
        price_native = pool.get("priceNative", "")
        price_usd = pool.get("priceUsd", "")
        liquidity_obj = pool.get("liquidity", {})
        liquidity_usd = liquidity_obj.get("usd", 0.0)
        market_cap = pool.get("marketCap", 0.0)
        pair_created_at = pool.get("pairCreatedAt", 0)

        # Extract websites and socials from the "info" object.
        info = pool.get("info", {})
        # For websites, the API returns an array; join them if available.
        websites_list = info.get("websites", [])
        if websites_list and isinstance(websites_list, list):
            # Each item is expected to be a dict with a "url" key.
            websites = ", ".join([item.get("url", "").strip() for item in websites_list if item.get("url")])
            if not websites:
                websites = "N/A"
        else:
            websites = "N/A"

        # For socials, iterate over the array to find Twitter and Telegram.
        socials = info.get("socials", [])
        twitter = "N/A"
        telegram = "N/A"
        if socials and isinstance(socials, list):
            for social in socials:
                social_type = social.get("type", "").lower()
                social_url = social.get("url", "").strip()
                if social_type == "twitter" and social_url:
                    twitter = social_url
                elif social_type == "telegram" and social_url:
                    telegram = social_url

        return {
            "dexscreener_url": dexscreener_url,
            "pair_address": pair_address,
            "price_native": price_native,
            "price_usd": price_usd,
            "liquidity": liquidity_usd,
            "market_cap": market_cap,
            "pair_created_at": pair_created_at,
            "websites": websites,
            "twitter": twitter,
            "telegram": telegram,
        }
    except Exception as e:
        print(f"Error fetching Dexscreener data for {mint_address}: {e}")
        return {}

# Example usage:
if __name__ == "__main__":
    test_mint = "2sCUCJdVkmyXp4dT8sFaA9LKgSMK4yDPi9zLHiwXpump"  # Example mint address for "Alpha"
    dex_data = get_dexscreener_data(test_mint)
    print(dex_data)
