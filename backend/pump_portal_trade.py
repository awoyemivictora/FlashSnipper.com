import requests
import os
from dotenv import load_dotenv

load_dotenv()

PUMPPORTAL_WALLET_PUBLIC_KEY = os.getenv("PUMPPORTAL_WALLET_PUBLIC_KEY")
PUMPPORTAL_WALLET_PRIVATE_KEY = os.getenv("PUMPPORTAL_WALLET_PRIVATE_KEY")
PUMPPORTAL_API_KEY = os.getenv("PUMPPORTAL_API_KEY")


def execute_trade(
    api_key: str,
    action: str,
    mint: str,
    amount,  # can be an int/float or a string if using a percentage (e.g. "100%")
    denominated_in_sol: str,  # "true" if amount is in SOL, "false" if amount is tokens
    slippage: int,
    priority_fee: float,
    pool: str = "pump",
    skip_preflight: str = "true"
):
    """
    Executes a trade (buy or sell) using the PumpPortal API.
    
    Parameters:
        api_key (str): Your PumpPortal API key.
        action (str): "buy" or "sell".
        mint (str): The contract address of the token to trade.
        amount: The amount of SOL or tokens to trade (or a percentage string if selling).
        denominated_in_sol (str): "true" if the amount is in SOL, "false" if it is in tokens.
        slippage (int): The percent slippage allowed.
        priority_fee (float): The amount to use to enhance transaction speed.
        pool (str): The pool to use ("pump", "raydium", or "auto"). Defaults to "pump".
        skip_preflight (str): "true" to skip simulation checks, "false" to simulate the transaction before sending.
        
    Returns:
        dict: The JSON response from the API (transaction signature or error details).
    """
    url = f"https://pumpportal.fun/api/trade?api-key={api_key}"
    payload = {
        "action": action,             # "buy" or "sell"
        "mint": mint,                 # token contract address (after the '/' in the Pump.fun URL)
        "amount": amount,             # amount of SOL or tokens to trade, or percentage if selling (e.g. "100%")
        "denominatedInSol": denominated_in_sol,  # "true" if the amount is SOL, "false" if tokens
        "slippage": slippage,         # allowed percent slippage
        "priorityFee": priority_fee,  # priority fee to speed up the transaction
        "pool": pool,                 # trading pool: "pump", "raydium", or "auto"
        "skipPreflight": skip_preflight  # simulation check: "true" to skip, "false" to simulate
    }
    
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()  # raise an exception for HTTP errors
        data = response.json()
        print("Trade response:", data)
        return data
    except requests.RequestException as e:
        print(f"Trade execution failed: {e}")
        return None

# Example usage:
if __name__ == "__main__":
    API_KEY = PUMPPORTAL_API_KEY
    token_mint = "HWVkqNGQJxewdkmgE5rsikoGULBnn7GN383ywG1Hpump"  # Replace with the token contract address

    trade_result = execute_trade(
        api_key=API_KEY,
        action="sell",                  # or "sell"
        mint=token_mint,
        amount=100,                 # For example, 100,000 tokens, or use "100%" for selling 100% of your tokens
        denominated_in_sol="false",    # "true" if the amount is SOL, "false" if tokens
        slippage=10,                   # Allowed slippage percentage
        priority_fee=0.005,            # Priority fee to help speed up the transaction
        pool="pump",                   # trading pool
        skip_preflight="true"          # Skip simulation check (set "false" to simulate before executing)
    )
