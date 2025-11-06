import json
import aiohttp
from fastapi import FastAPI, HTTPException
from datetime import datetime, timedelta
from pydantic import BaseModel
import requests
import os
from dotenv import load_dotenv
import asyncio
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
import websockets
from app.telegramMessageFormatter import send_buy_telegram_notification, send_sell_telegram_notification, send_telegram_notification
import logging


# Create a custom logger for your bot
logger = logging.getLogger("bot_logger")
logger.setLevel(logging.INFO)  # Set minimum level to INFO (captures INFO and ERROR)

# Create a file handler (optional, if you want logs saved)
file_handler = logging.FileHandler("bot.log")
file_handler.setLevel(logging.INFO)

# Create a console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Define a simple log format
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Suppress third-party logs (SQLAlchemy, PostgreSQL, FastAPI)
logging.getLogger("sqlalchemy").setLevel(logging.CRITICAL)
logging.getLogger("uvicorn").setLevel(logging.CRITICAL)
logging.getLogger("fastapi").setLevel(logging.CRITICAL)
logging.getLogger("asyncpg").setLevel(logging.CRITICAL)  # PostgreSQL driver
logging.getLogger("httpx").setLevel(logging.CRITICAL)    # HTTP requests if used


load_dotenv()


# Import your models and database configuration.
from . import models, database

# Load your environment variables and API keys.
SOLSCAN_API_KEY = os.getenv("SOLSCAN_API_KEY")

# Read Telegram config from env variables.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


PUMPPORTAL_WALLET_PUBLIC_KEY = os.getenv("PUMPPORTAL_WALLET_PUBLIC_KEY")
PUMPPORTAL_WALLET_PRIVATE_KEY = os.getenv("PUMPPORTAL_WALLET_PRIVATE_KEY")
PUMPPORTAL_API_KEY = os.getenv("PUMPPORTAL_API_KEY")


app = FastAPI()


# Database setup
models.Base.metadata.create_all(bind=database.engine)


PRICE_CACHE = {}   # Key: token.mint_address, Value: last observed price
HOLDER_CACHE = {}  # Key: token.mint_address, Value: last observed holder count


# -------------------------------
# Pydantic Models
# -------------------------------
class TokenInput(BaseModel):
    mint_address: str




# # -------------------------------
# # Helper Function: Get Mint token data from Dexscreener 
# # -------------------------------

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
        logger.error(f"Error fetching Dexscreener data for {mint_address}: {e}")
        return {}



#============================ ALL ENDPOINTS STARTS HERE ========================

# -------------------------------
# Endpoint: Health Check
# -------------------------------
@app.get("/")
def root():
    return {"status": "API is running"}


# -------------------------------
# Endpoint: Fetch Token Metadata
# (Existing GET endpoint – can be used for manual testing)
# -------------------------------
@app.get("/fetch-token-metadata/{mint_address}")
def fetch_token_metadata(mint_address: str):
    """
    Fetches token metadata from Solscan and stores it in the database.
    """
    url = "https://pro-api.solscan.io/v2.0/token/meta"
    params = {"address": mint_address}
    headers = {
        "Accept": "application/json",
        "token": SOLSCAN_API_KEY
    }

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # Raise exception for HTTP errors
        metadata = response.json()

        if not metadata.get("success"):
            raise HTTPException(status_code=404, detail="Token metadata not found")

        data = metadata["data"]

        # Create a TokenMetadata object (adjust field mapping as needed)
        token_metadata = models.TokenMetadata(
            mint_address=data.get("address"),
            supply=data.get("supply"),
            name=data.get("name"),
            symbol=data.get("symbol"),
            icon=data.get("icon"),
            decimals=data.get("decimals"),
            holder=data.get("holder"),
            creator=data.get("creator"),
            create_tx=data.get("create_tx"),
            created_time=data.get("created_time"),
            first_mint_tx=data.get("first_mint_tx"),
            first_mint_time=data.get("first_mint_time"),
            volume_24h=data.get("volume_24h"),
            price_change_24h=data.get("price_change_24h"),
            timestamp=datetime.utcnow(),
        )

        # Save/update the token metadata in the database.
        with database.SessionLocal() as db:
            db.merge(token_metadata)
            db.commit()

        return {"status": "success", "data": data}

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching token metadata: {e}")


# -------------------------------
# Endpoint: Process New Token from Pumpportal query
# This endpoint combines Pumpportal ingestion with Solscan metadata fetching.
# -------------------------------
@app.post("/process-token")
def process_token(token_input: TokenInput):
    """
    Accepts a token (mint address) from Pumpportal, fetches metadata from Solscan,
    and stores/updates it in the database.
    """
    mint_address = token_input.mint_address

    # Call the Solscan API to fetch metadata.
    url = "https://pro-api.solscan.io/v2.0/token/meta"
    params = {"address": mint_address}
    headers = {
        "Accept": "application/json",
        "token": SOLSCAN_API_KEY
    }

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        metadata = response.json()

        if not metadata.get("success"):
            raise HTTPException(status_code=404, detail="Token metadata not found from Solscan")

        data = metadata["data"]

        # Build the TokenMetadata instance from the fetched data.
        token_metadata = models.TokenMetadata(
            mint_address=data.get("address"),
            supply=data.get("supply"),
            name=data.get("name"),
            symbol=data.get("symbol"),
            icon=data.get("icon"),
            decimals=data.get("decimals"),
            holder=data.get("holder"),
            creator=data.get("creator"),
            create_tx=data.get("create_tx"),
            created_time=data.get("created_time"),
            first_mint_tx=data.get("first_mint_tx"),
            first_mint_time=data.get("first_mint_time"),
            volume_24h=data.get("volume_24h"),
            price_change_24h=data.get("price_change_24h"),
            timestamp=datetime.utcnow()
        )

        # Save the metadata to the database.
        with database.SessionLocal() as db:
            db.merge(token_metadata)
            db.commit()

        return {"status": "success", "data": data}

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error processing token: {e}")


# -------------------------------
# (Optional) Additional Endpoints
# -------------------------------

@app.get("/tokens/{mint_address}")
def get_token(mint_address: str):
    """
    Retrieve token metadata from the database.
    """
    with database.SessionLocal() as db:
        token = db.query(models.TokenMetadata).filter(models.TokenMetadata.mint_address == mint_address).first()
        if not token:
            raise HTTPException(status_code=404, detail="Token not found")
        return {"status": "success", "data": token.to_dict()}


@app.get("/sniping-candidates")
def sniping_candidates():
    """
    Retrieve tokens that meet your sniping criteria.
    (Filtering logic can be expanded based on candidate analysis.)
    """
    with database.SessionLocal() as db:
        candidates = db.query(models.TokenMetadata).filter(models.TokenMetadata.is_candidate == True).all()
    return {"status": "success", "candidates": [token.to_dict() for token in candidates]}










#============================= TRADE EXECUTION LOGIC STARTS HERE =================



############################################################
# 1. Synchronous Trade Execution Function (Provided)
############################################################
def execute_trade(
    api_key: str,
    action: str,
    mint: str,
    amount,  # e.g., an integer/float or a string like "100%"
    denominated_in_sol: str,  # "true" if amount is in SOL, "false" if it’s tokens
    slippage: int,
    priority_fee: float,
    pool: str = "raydium", # pump, raydium, auto
    skip_preflight: str = "true"
):
    """
    Executes a trade (buy or sell) using the PumpPortal API.
    """
    url = f"https://pumpportal.fun/api/trade?api-key={api_key}"
    payload = {
        "action": action,             # "buy" or "sell"
        "mint": mint,                 # token contract address (after the '/' in the Pump.fun URL)
        "amount": amount,             # amount of SOL or tokens to trade (or percentage string if selling)
        "denominatedInSol": denominated_in_sol,  # "true" if SOL, "false" if tokens
        "slippage": slippage,         # allowed percent slippage
        "priorityFee": priority_fee,  # fee to speed up the transaction
        "pool": pool,                 # trading pool: "pump", "raydium", or "auto"
        "skipPreflight": skip_preflight  # "true" to skip simulation, "false" to simulate
    }
    
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()  # raise an exception for HTTP errors
        data = response.json()
        logger.info("Trade response:", data)
        return data
    except requests.RequestException as e:
        logger.error(f"Trade execution failed: {e}")
        return None



############################################################
# 2. Asynchronous Wrapper for execute_trade
############################################################
TRADE_SLIPPAGE = 10
PRIORITY_FEE = 0.005
TRADE_POOL = "pump"

async def execute_trade_async(action: str, mint: str, amount, denominated_in_sol: str):
    """
    Wraps the synchronous execute_trade() function so it can be called asynchronously.
    """
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        execute_trade,
        PUMPPORTAL_API_KEY,
        action,
        mint,
        amount,
        denominated_in_sol,
        TRADE_SLIPPAGE,
        PRIORITY_FEE,
        TRADE_POOL,
        "true"  # skipPreflight; adjust as needed
    )
    return result





############################################################
# 3. Pumpportal Subscription and Event Processing
############################################################
async def pumpportal_subscription_loop():
    """
    Runs the Pumpportal subscription continuously.
    """
    while True:
        try:
            await pumpportal_subscription()
        except Exception as e:
            logger.error(f"Pumpportal subscription error: {e}")
        # Wait a few seconds before reconnecting.
        await asyncio.sleep(90)



async def pumpportal_subscription():
    """
    Connects to Pumpportal's WebSocket, subscribes to new token events,
    processes one event, then disconnects.
    """
    uri = "wss://pumpportal.fun/api/data"
    async with websockets.connect(uri) as websocket:
        # Subscribe to token creation events.
        payload = {"method": "subscribeNewToken"}
        await websocket.send(json.dumps(payload))

        # Optionally, subscribe to other events if needed.
        payload_trade = {
            "method": "subscribeTokenTrade",
            "keys": ["91WNez8D22NwBssQbkzjy4s2ipFrzpmn5hfvWVe2aY5p"]
        }
        await websocket.send(json.dumps(payload_trade))
        
        # Loop until we receive a pump event (an event that contains the "mint" key).
        while True:
            message = await websocket.recv()
            event = json.loads(message)
            logger.info("Received Pumpportal event:", event)

            # Skip non-token events (like subscription confirmation messages)
            if "mint" not in event:
                continue

            await process_pumpportal_event(event)
            break  # Process one event per connection



async def process_pumpportal_event(event: dict):
    """
    Processes a Pumpportal event:
      - Saves the token trade in the database.
      - Waits a delay (e.g., 80 seconds) before enriching token metadata.
      - After enrichment, you may decide to execute a buy trade.
    """
    try:
        # Extract values from the event.
        signature = event.get("signature")
        mint = event.get("mint")  # This will become our mint_address

        # Skip if mint is missing or equals the native null address.
        if not mint or mint == "11111111111111111111111111111111":
            logger.info("Skipping event due to missing or native null mint address.")
            return

        trader_public_key = event.get("traderPublicKey")
        tx_type = event.get("txType")
        initial_buy = event.get("initialBuy")
        sol_amount = event.get("solAmount")
        bonding_curve_key = event.get("bondingCurveKey")
        v_tokens_in_bonding_curve = event.get("vTokensInBondingCurve")
        v_sol_in_bonding_curve = event.get("vSolInBondingCurve")
        market_cap_sol = event.get("marketCapSol")
        name = event.get("name")
        symbol = event.get("symbol")
        uri = event.get("uri")
        pool = event.get("pool")
        timestamp = datetime.utcnow()

        # Create an instance of NewTokens with the extracted values.
        token_trade = models.NewTokens(
            mint_address=mint,
            name=name,
            symbol=symbol,
            timestamp=timestamp,
            signature=signature,
            trader_public_key=trader_public_key,
            tx_type=tx_type,
            initial_buy=initial_buy,
            sol_amount=sol_amount,
            bonding_curve_key=bonding_curve_key,
            v_tokens_in_bonding_curve=v_tokens_in_bonding_curve,
            v_sol_in_bonding_curve=v_sol_in_bonding_curve,
            market_cap_sol=market_cap_sol,
            uri=uri,
            pool=pool
        )
        
        # Save the record into the NewTokens table.
        with database.SessionLocal() as db:
            db.merge(token_trade)
            db.commit()
        logger.info(f"Successfully processed Pumpportal event for token: {mint}")

        # Wait before calling the metadata enrichment
        await asyncio.sleep(80)
        await process_token_logic(mint)

    except Exception as e:
        logger.error(f"Error processing Pumpportal event for token: {event.get('mint')}: {e}")






############################################################
# 4. Token Metadata Enrichment
############################################################
async def process_token_logic(mint: str):
    """
    Synchronously calls the Solscan API to fetch token metadata,
    Retrieves additional data from Dexscreener, and saves/updates the data in the database.
    Falls back to the provided mint_address if Solscan does not return an address.
    """
    url = "https://pro-api.solscan.io/v2.0/token/meta"
    params = {"address": mint}
    headers = {
        "Accept": "application/json",
        "token": SOLSCAN_API_KEY  # Using the 'token' header as required by Solscan
    }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        metadata = response.json()
        logger.info(f"Solscan metadata gotten: {metadata}")

        if not metadata.get("success"):
            logger.info(f"Token metadata not found for {mint}")
            return

        # At this point, we have valid metadata.
        data = metadata["data"]

        # Use the address from Solscan if available; otherwise, use the provided mint_address.
        # token_mint = data.get("address") or mint_address

        token_metadata = models.TokenMetadata(
            mint_address=mint,
            supply=data.get("supply"),
            name=data.get("name"),
            symbol=data.get("symbol"),
            icon=data.get("icon"),
            decimals=data.get("decimals"),
            holder=data.get("holder"),
            creator=data.get("creator"),
            create_tx=data.get("create_tx"),
            created_time=data.get("created_time"),
            first_mint_tx=data.get("first_mint_tx"),
            first_mint_time=data.get("first_mint_time"),
            volume_24h=data.get("volume_24h"),
            price_change_24h=data.get("price_change_24h"),
            timestamp=datetime.utcnow(),
        )

        # Fetch additional data from Dexscreener.
        dex_data = get_dexscreener_data(mint)
        if dex_data:
            token_metadata.liquidity = dex_data.get("liquidity")
            token_metadata.dexscreener_url = dex_data.get("dexscreener_url")
            token_metadata.pair_address = dex_data.get("pair_address")
            token_metadata.price_native = dex_data.get("price_native")
            token_metadata.price_usd = dex_data.get("price_usd")
            # Optionally, you can override the market cap with the Dexscreener value.
            token_metadata.market_cap = dex_data.get("market_cap") or data.get("market_cap")
            token_metadata.pair_created_at = dex_data.get("pair_created_at")
            token_metadata.websites = dex_data.get("websites")
            token_metadata.twitter = dex_data.get("twitter")
            token_metadata.telegram = dex_data.get("telegram")
        else:
            token_metadata.liquidity = 0.0

        with database.SessionLocal() as db:
            db.merge(token_metadata)
            db.commit()

        logger.info(f"Successfully processed token: {mint}")

    except requests.RequestException as e:
        logger.error(f"Error fetching token metadata for {mint}: {e}")
    except Exception as ex:
        logger.error(f"Error processing token {mint}: {ex}")





############################################################
# 5a. Rugcheck Analysis
############################################################
async def check_rug(mint: str):
    """
    Checks the rug risk of a token using the RugCheck API.
    """
    url = f"https://api.rugcheck.xyz/v1/tokens/{mint}/report/summary"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data # Return RugCheck report
                else:
                    error_message = await response.text()
                    logger.error(f"Error checking RugCheck API for {mint}: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Failed to connect to RugCheck API for {mint}: {e}")
        return None



############################################################
# 5b. Candidate Analysis (Improved)
############################################################

async def analyze_candidates():
    """
    Periodically analyzes tokens to find candidates that meet these requirements:
      - Created more than 15 minutes ago but less than 72 hours ago
      - At least 10 holders
      - Market cap of at least 15,000
      - Passes RugCheck
    Once a valid candidate is found, it sends a Telegram notification,
    executes a buy order, waits 30 seconds, executes a sell order, and
    notifies via Telegram again.
    """
    global PRICE_CACHE, HOLDER_CACHE

    while True:
        try:
            with database.SessionLocal() as db:
                now = datetime.utcnow()
                tokens = db.query(models.TokenMetadata).filter(models.TokenMetadata.mint_address.isnot(None)).all()

                for token in tokens:
                    # Determine deployment time
                    deployed_time = datetime.utcfromtimestamp(token.created_time) if token.created_time else now
                    age = now - deployed_time

                    # Ensure token is within the valid time frame (more than 15 minutes but less than 72 hours old)
                    if age < timedelta(minutes=15) or age > timedelta(hours=72):
                        token.is_candidate = False
                        token.is_notified = False
                        PRICE_CACHE.pop(token.mint_address, None)
                        HOLDER_CACHE.pop(token.mint_address, None)
                        db.commit() # Commit change
                        continue

                    # Ensure token has at least 20 holders
                    if token.holder is None or token.holder < 20:
                        token.is_candidate = False
                        token.is_notified = False
                        db.commit() # Commit change
                        continue

                    # Ensure market cap is at least 15,000
                    token.market_cap = float(token.market_cap) if token.market_cap is not None else 0
                    if token.market_cap < 30000:
                        token.is_candidate = False
                        token.is_notified = False
                        db.commit() # Commit change
                        continue

                    # RugCheck API verification
                    rug_data = await check_rug(token.mint_address)
                    if rug_data and "score" in rug_data and rug_data["score"] < 100:
                        logger.info(f"Token {token.mint_address} passes RugCheck with score {rug_data['score']}.")
                    else:
                        logger.warning(f"Skipping {token.mint_address} due to high RugCheck score or failed RugCheck API.")
                        token.is_candidate = False
                        token.is_notified = False
                        db.commit() # Commit change
                        continue

                    # If token meets all criteria, mark as a candidate
                    if not token.is_candidate:
                        token.is_candidate = True 
                        db.commit() # Commit change 

                    # Send Telegram notification if not already notified
                    if not token.is_notified:
                        success = await send_telegram_notification(token)
                        if success:
                            token.is_notified = True  
                            db.commit() # Commit the change
                        else:
                            logger.error(f"Failed to send Telegram notification for {token.mint_address}")
                            continue  # Skip buying if notification fails

                    # Buy the token if it's a valid candidate (ensuring it only buys once)
                    if token.is_candidate and not token.entry_price:
                        logger.info(f"Executing BUY for token {token.mint_address} at price {token.price_usd}")
                        trade_signature = await execute_trade_async("buy", token.mint_address, 100, "false")

                        if isinstance(trade_signature, dict):  
                            trade_signature = json.dumps(trade_signature)

                        # Store entry price and update DB
                        token.entry_price = token.price_usd

                        # Send BUY trade notification
                        await send_buy_telegram_notification(token)
                        logger.info("Buy telegram notification sent successfully")

                        # Commit the database change after buying
                        db.commit()

                        # Wait for 30 seconds before selling
                        await asyncio.sleep(30)

                        # # Fetch updated price (assumes token.price_usd is updated every loop)
                        # sell_price = token.price_usd  # Save sell price

                        # # Execute SELL trade after 30 seconds
                        # logger.info(f"Executing SELL for token {token.mint_address}")
                        # sell_trade_signature = await execute_trade_async("sell", token.mint_address, 100, "false")
                        # logger.info(f"Sell trade signature: {sell_trade_signature}")

                        # # Calculate Profit
                        # sell_price = float(token.price_usd)  # Ensure it's a float
                        # entry_price = float(token.entry_price)  # Convert to float in case it's stored as a string
                        # profit = (sell_price - entry_price) * (100 / entry_price)  # Assuming $100 investment
                        # logger.info(f"Calculated profit for {token.mint_address}: {profit}")

                        # # Send SELL trade notification
                        # logger.info(f"Attempting to send SELL trade notification for {token.mint_address} with profit: {profit}")
                        # try:
                        #     await send_sell_telegram_notification(token, profit)
                        #     logger.info("Sell telegram notification sent successfully")
                        # except Exception as e:
                        #     logger.error(f"Failed to send SELL telegram notification for {token.mint_address}: {e}")



                        # Fetch updated price (ensure it's converted to float)
                        sell_price = float(token.price_usd) if token.price_usd else 0.0

                        # Ensure entry price is a float
                        entry_price = float(token.entry_price) if token.entry_price else 0.0

                        # Execute SELL trade
                        logger.info(f"Executing SELL for token {token.mint_address}")
                        sell_trade_signature = await execute_trade_async("sell", token.mint_address, 100, "false")
                        logger.info(f"Sell trade signature: {sell_trade_signature}")

                        # Ensure valid price before calculating profit
                        if entry_price > 0:
                            profit = (sell_price - entry_price) * (100 / entry_price)  # Assuming $100 investment
                        else:
                            profit = 0.0  # Avoid division by zero

                        logger.info(f"Calculated profit for {token.mint_address}: {profit}")

                        # Send SELL trade notification
                        logger.info(f"Attempting to send SELL trade notification for {token.mint_address} with profit: {profit}")
                        try:
                            await send_sell_telegram_notification(token, profit)
                            logger.info("Sell telegram notification sent successfully")
                        except Exception as e:
                            logger.error(f"Failed to send SELL telegram notification for {token.mint_address}: {e}")


                        logger.info(f"Token {token.mint_address} successfully bought and sold after 30 seconds. Profit: ${profit:.2f}")

                        # # Reset token state after trade
                        # token.entry_price = None
                        # token.is_candidate = False
                        # token.is_notified = False

                        # # Commit database changes after selling
                        # db.commit()

                logger.info("Candidate analysis complete.")

        except Exception as e:
            logger.error(f"Error during candidate analysis: {e}")

        await asyncio.sleep(900) # Wait 15 minutes (900 seconds) before running again



############################################################
# 6. Trade Monitoring for Stop Loss / Take Profit
############################################################

# async def monitor_trade(mint: str, entry_price: float):
#     """
#     Monitors the token's price and triggers a sell trade when:
#       - Price drops to 50% of the entry price → Sell 100 tokens
#       - Price reaches 200% (2x entry) → Sell 50 tokens
#       - Price reaches 300% (3x entry) → Sell remaining 500 tokens
#     After executing the sell trade, a Telegram notification is sent.
#     """
#     CHECK_INTERVAL = 10  # seconds between price checks
#     reason = None  # Will be set to "Stop Loss", "Take Profit", etc.
#     sold_50 = False # Track if 50 tokens have been sold at 2x price
#     sold_100 = False # Track if 100 tokens have been sold at 0.5x price

#     try:
#         entry_price = float(entry_price)  # Ensure entry_price is converted to float
#     except ValueError:
#         logger.error(f"Invalid entry_price: {entry_price}. Must be a float.")
#         return
    

#     while True:
#         dex_data = get_dexscreener_data(mint)  # expects a dict with "price_usd"
        
#         current_price = float(dex_data.get("price_usd", 0))  # Ensure conversion to float
#         if current_price is None:
#             logger.info(f"Price data not available for {mint}. Retrying...")
#             await asyncio.sleep(CHECK_INTERVAL)
#             continue

#         logger.info(f"Monitoring {mint}: Entry Price = {entry_price}, Current Price = {current_price}")


#         # Stop Loss: Sell 100 tokens if price drops to 50% of entry price
#         if current_price <= entry_price * 0.5 and not sold_100:
#             reason = "Stop Loss"
#             logger.info(f"Stop Loss triggered for {mint}. Selling 100 tokens.")
#             await execute_trade_async("sell", mint, 100, "false")
#             await send_sell_telegram_notification(mint)
#             break # Exit loop since all tokens are sold at 50% loss

#         # Take Profit (2x): Sell 50 tokens if price reaches 2x entry price
#         elif current_price >= entry_price * 2.0 and not sold_50:
#             reason = "Take Profit (2x)"
#             logger.info(f"Take Profit triggered for {mint}. Executing remaining 50 tokens.")
#             await execute_trade_async("sell", mint, 50, "false")
#             await send_sell_telegram_notification(mint)
#             sold_50 = True # Mark as sold

#         # Final Profit (3x): Sell remaining 500 tokens if price reaches 3x entry price
#         elif current_price >= entry_price * 3.0:
#             reason = "Take Profit (3x)"
#             logger.info(f"Take Profit at 3x triggered for {mint}. Selling remaining 50 tokens.")
#             await execute_trade_async("sell", mint, 50, "false")
#             await send_sell_telegram_notification(mint)
#             break # Exit loop after final sale

#         await asyncio.sleep(CHECK_INTERVAL)





############################################################
# 7. Liquidity Updates (as before)
############################################################

async def update_liquidity():
    """
    Periodically updates the liquidity field for all tokens in the database by querying Dexscreener.
    """
    while True:
        try:
            with database.SessionLocal() as db:
                tokens = db.query(models.TokenMetadata).all()
                for token in tokens:
                    new_data = get_dexscreener_data(token.mint_address)
                    if new_data:
                        token.liquidity = new_data.get("liquidity")
                        token.dexscreener_url = new_data.get("dexscreener_url")
                        token.pair_address = new_data.get("pair_address")
                        token.price_native = new_data.get("price_native")
                        token.price_usd = new_data.get("price_usd")
                        token.market_cap = new_data.get("market_cap")
                        token.pair_created_at = new_data.get("pair_created_at")
                        token.websites = new_data.get("websites")
                        token.twitter = new_data.get("twitter")
                        token.telegram = new_data.get("telegram")
                    else:
                        logger.error("No Dexscreener data for token: %s", token.mint_address)
                db.commit()
                logger.info("Liquidity update complete.")
        except SQLAlchemyError as e:
            logger.error("Error updating liquidity: %s", e)
        except Exception as ex:
            logger.error("Unexpected error updating liquidity: %s", ex)
        # Run every 10 minutes. (600)
        await asyncio.sleep(25)









############################################################
# IMPROVEMENTS
############################################################


































############################################################
# 8. FastAPI Application Lifespan (Background Tasks)
############################################################
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    # Start the Pumpportal subscription loop.
    asyncio.create_task(pumpportal_subscription_loop())
    # Start candidate analysis and liquidity update background jobs.
    asyncio.create_task(analyze_candidates())
    asyncio.create_task(update_liquidity())
    yield
    logger.info("Shutting down...")
    
# Re-initialize FastAPI with the lifespan manager.
app = FastAPI(lifespan=lifespan)


