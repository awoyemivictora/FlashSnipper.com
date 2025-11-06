import requests

def get_ray_liquidity(mint_address: str) -> float:
    """
    Calls the Raydium API V3 endpoint '/pools/info/mint' to fetch pool info for a given token mint.
    First tries with the query parameter 'mint1'. If no pool is found, it then tries with 'mint2'.
    Uses the 'tvl' field if 'liquidity' is not provided.
    
    Returns:
        A float representing the liquidity (or TVL) from the first pool found, or 0.0 if none are found.
    """
    
    def try_query(query_param: str, page: int = 1) -> float:
        url = (
            f"https://api-v3.raydium.io/pools/info/mint?"
            f"{query_param}={mint_address}&poolType=all&poolSortField=default&sortType=desc&pageSize=10&page={page}"
        )
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            # Debug: Uncomment to print full response:
            # print(f"Response using {query_param} for mint {mint_address} on page {page}:", data)
            if data.get("success"):
                pool_info = data.get("data", {})
                if pool_info.get("count", 0) > 0:
                    pools = pool_info.get("data", [])
                    first_pool = pools[0]
                    # Try "liquidity" first; if not available, use "tvl"
                    liquidity = first_pool.get("liquidity")
                    if liquidity is None:
                        liquidity = first_pool.get("tvl", 0.0)
                    return float(liquidity)
        except Exception as e:
            print(f"Error fetching liquidity with {query_param} for {mint_address}: {e}")
        return 0.0

    # First, try using 'mint1'
    liquidity = try_query("mint1", page=1)
    if liquidity > 0:
        return liquidity

    # If nothing found, try using 'mint2'
    liquidity = try_query("mint2", page=1)
    return liquidity

# Example usage:
if __name__ == "__main__":
    test_mint = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"  # USDT mint address
    liquidity = get_ray_liquidity(test_mint)
    print(f"Liquidity for {test_mint}: {liquidity}")
