from fastapi import FastAPI, HTTPException
from datetime import datetime, timedelta
from pydantic import BaseModel
import requests
import os
import asyncio
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session

from app.telegramMessageFormatter import format_telegram_message

# Import your models and database configuration.
from . import models, database

# Load your environment variables and API keys.
SOLSCAN_API_KEY = os.getenv("SOLSCAN_API_KEY")
BITQUERY_WS_URL = os.getenv("BITQUERY_WS_URL")

# Read Telegram config from env variables.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


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



def send_telegram_notification(token):
    """
    Sends a Telegram notification with candidate token details.
    """
    message = format_telegram_message(token)
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "MarkdownV2"  # Using MarkdownV2 so ensure proper escaping.
    }
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        print(f"Telegram notification sent for token: {token.mint_address}")
    except Exception as e:
        print(f"Error sending Telegram notification for {token.mint_address}: {e}")

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
        print(f"Error fetching Dexscreener data for {mint_address}: {e}")
        return {}

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
            price=data.get("price"),
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
# Endpoint: Process New Token from Bitquery
# This endpoint combines Bitquery ingestion with Solscan metadata fetching.
# -------------------------------
@app.post("/process-token")
def process_token(token_input: TokenInput):
    """
    Accepts a token (mint address) from Bitquery, fetches metadata from Solscan,
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
            price=data.get("price"),
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



# -------------------------------
# Background Bitquery Subscription (for reference)
# -------------------------------
async def bitquery_subscription_loop():
    """
    Runs the Bitquery subscription every 30 seconds.
    """
    while True:
        try:
            await start_bitquery_subscription()
        except Exception as e:
            print(f"Bitquery subscription error: {e}")
        await asyncio.sleep(30)  # Wait for 30 seconds before restarting



async def start_bitquery_subscription():
    """
    Subscribes to Bitquery's WebSocket feed and processes real-time data.
    """
    from gql import gql
    from gql.transport.websockets import WebsocketsTransport

    transport = WebsocketsTransport(
        url=BITQUERY_WS_URL,
        headers={"Sec-WebSocket-Protocol": "graphql-ws"},
    )
    await transport.connect()
    print("Connected to Bitquery WebSocket")

    query = gql(
        """
        query MyQuery($time_1h_ago: DateTime) {
            Solana {
                DEXTradeByTokens(
                    where: {
                        Trade: {
                            Dex: { ProtocolName: { is: "pump" } }
                        }
                        Block: { Time: { since: $time_1h_ago } }
                    }
                    limit: {count: 10}
                ) {
                    Trade {
                        Currency {
                            Name
                            Symbol
                            MintAddress
                        }
                        PriceInUSD
                    }
                    volume: sum(of: Trade_Side_AmountInUSD)
                }
            }
        }
        """
    )

    async def process_subscription():
        try:
            async for result in transport.subscribe(query):
                await handle_bitquery_data(result)
        except asyncio.CancelledError:
            print("Bitquery subscription cancelled.")
        finally:
            await transport.close()

    asyncio.create_task(process_subscription())



def process_token_logic(mint_address: str):
    """
    Synchronously calls the Solscan API to fetch token metadata,
    retrieves additional data from Dexscreener,
    and saves/updates the data in the database.
    """
    url = "https://pro-api.solscan.io/v2.0/token/meta"
    params = {"address": mint_address}
    headers = {
        "Accept": "application/json",
        "token": SOLSCAN_API_KEY  # Using the 'token' header as required by Solscan
    }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        metadata = response.json()

        if not metadata.get("success"):
            print(f"Token metadata not found for {mint_address}")
            return

        data = metadata["data"]

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
            price=data.get("price"),
            volume_24h=data.get("volume_24h"),
            price_change_24h=data.get("price_change_24h"),
            timestamp=datetime.utcnow(),
        )

        # Instead of calling get_ray_liquidity, now fetch full Dexscreener data.
        dex_data = get_dexscreener_data(mint_address)
        if dex_data:
            token_metadata.liquidity = dex_data.get("liquidity")
            # Update additional Dexscreener fields.
            token_metadata.dexscreener_url = dex_data.get("dexscreener_url")
            token_metadata.pair_address = dex_data.get("pair_address")
            token_metadata.price_native = dex_data.get("price_native")
            token_metadata.price_usd = dex_data.get("price_usd")
            token_metadata.liquidity = dex_data.get("liquidity")
            token_metadata.market_cap = dex_data.get("market_cap")  # Optionally override Solscan value if needed.
            token_metadata.pair_created_at = dex_data.get("pair_created_at")
            token_metadata.websites = dex_data.get("websites")
            token_metadata.twitter = dex_data.get("twitter")
            token_metadata.telegram = dex_data.get("telegram")
        else:
            # Fallback: If no Dexscreener data, you could set liquidity to 0 or call an alternative function.
            token_metadata.liquidity = 0.0

        with database.SessionLocal() as db:
            db.merge(token_metadata)
            db.commit()

        print(f"Successfully processed token: {mint_address}")

    except requests.RequestException as e:
        print(f"Error fetching token metadata for {mint_address}: {e}")
    except Exception as ex:
        print(f"Error processing token {mint_address}: {ex}")



async def handle_bitquery_data(data):
    """
    Processes Bitquery WebSocket data by:
      1. Saving each unique token trade to the database.
      2. Fetching additional token metadata from Solscan.
    """
    print("Received data from Bitquery:", data)

    # Ensure that the data payload contains our expected information.
    if hasattr(data, 'data') and data.data:
        solana_data = data.data.get("Solana", {}).get("DEXTradeByTokens", [])
        unique_trades = {}  # Dictionary keyed by mint_address

        # Process each trade in the subscription data.
        for trade in solana_data:
            trade_info = trade.get("Trade", {})
            currency = trade_info.get("Currency", {})
            mint_address = currency.get("MintAddress")

            # Skip if mint_address is the native null address.
            if mint_address == "11111111111111111111111111111111":
                print("Skipping native null mint address.")
                continue

            if not mint_address:
                print("Missing MintAddress; skipping trade.")
                continue

            try:
                # Create the trade record from Bitquery data.
                token_trade = models.NewTokens(
                    mint_address=mint_address,
                    name=currency.get("Name"),
                    symbol=currency.get("Symbol"),
                    price_in_usd=float(trade_info.get("PriceInUSD", 0)),
                    volume=float(trade.get("volume", 0)),
                    liquidity=0.0,  # Default value
                    timestamp=datetime.utcnow(),
                )
            except Exception as e:
                print(f"Error creating NewTokens for {mint_address}: {e}")
                continue

            # Deduplicate by mint_address.
            unique_trades[mint_address] = token_trade

        # Save all unique token trades into the database.
        if unique_trades:
            with database.SessionLocal() as db:
                try:
                    for token_trade in unique_trades.values():
                        db.merge(token_trade)
                    db.commit()
                    print(f"Upserted {len(unique_trades)} token trades from Bitquery.")
                except Exception as e:
                    print("Error during upsert of token trades:", e)
                    db.rollback()

        # For each unique token, fetch and store additional metadata from Solscan.
        for mint_address in unique_trades.keys():
            print(f"Processing Solscan metadata for token: {mint_address}")
            # Since process_token_logic is blocking, run it in an executor.
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, process_token_logic, mint_address)


# -------------------------------
# Background Job: Historical Data & Candidate Analysis
# -------------------------------
# async def analyze_candidates():
#     """
#     Periodically analyze tokens for historical trends and flag them as candidates.
#     Criteria (example):
#       - Price surge of at least 50% in the last 5 minutes.
#       - Holder increase of at least +10 in the last 5 minutes.
#       - Deployment between 15 minutes and 72 hours ago.
#     """
#     while True:
#         try:
#             with database.SessionLocal() as db:
#                 now = datetime.utcnow()
#                 for token in db.query(models.TokenMetadata).all():
#                     # Convert created_time (epoch) to datetime if available, else use now.
#                     deployed_time = datetime.utcfromtimestamp(token.created_time) if token.created_time else now

#                     # Check deployment window.
#                     if (now - deployed_time) < timedelta(minutes=15) or (now - deployed_time) > timedelta(hours=72):
#                         token.is_candidate = False
#                         token.is_notified = False
#                         continue

#                     # Calculate price surge.
#                     if token.last_price and token.last_price > 0:
#                         price_surge = ((token.price - token.last_price) / token.last_price) * 100
#                     else:
#                         price_surge = 0

#                     # Calculate holders surge.
#                     if token.last_holder is not None:
#                         holders_surge = token.holder - token.last_holder
#                     else:
#                         holders_surge = 0

#                     # Determine candidate status.
#                     candidate_status = (price_surge >= 50 and holders_surge >= 10)

#                     if candidate_status:
#                         # If the token just became a candidate and hasn't been notified, then notify.
#                         if not token.is_candidate and not token.is_notified:
#                             token.is_candidate = True
#                             token.is_notified = True
#                             # Send Telegram notification in a non-blocking way.
#                             loop = asyncio.get_running_loop()
#                             await loop.run_in_executor(None, send_telegram_notification, token)
#                         else:
#                             # Already candidate, ensure the flag remains true.
#                             token.is_candidate = True
#                     else:
#                         # Not a candidate: reset both flags.
#                         token.is_candidate = False
#                         token.is_notified = False

#                     # Update last_price and last_holder for next iteration.
#                     token.last_price = token.price
#                     token.last_holder = token.holder

#                 db.commit()
#                 print("Candidate analysis complete.")
#         except Exception as e:
#             print("Error during candidate analysis:", e)
#         # Run every 5 minutes.
#         await asyncio.sleep(300)

async def analyze_candidates():
    """
    Periodically analyze tokens for historical trends and flag them as candidates.
    Criteria (example):
      - Price surge of at least 50% in the last 5 minutes.
      - Holder increase of at least +10 in the last 5 minutes.
      - Deployment between 15 minutes and 72 hours ago.
    Uses in-memory caches (PRICE_CACHE and HOLDER_CACHE) to track previous values.
    """
    global PRICE_CACHE, HOLDER_CACHE

    while True:
        try:
            with database.SessionLocal() as db:
                now = datetime.utcnow()
                for token in db.query(models.TokenMetadata).all():
                    # Convert created_time (epoch) to datetime if available, else use now.
                    deployed_time = datetime.utcfromtimestamp(token.created_time) if token.created_time else now

                    # Check deployment window.
                    if (now - deployed_time) < timedelta(minutes=15) or (now - deployed_time) > timedelta(hours=72):
                        token.is_candidate = False
                        token.is_notified = False
                        # Remove from caches if present.
                        PRICE_CACHE.pop(token.mint_address, None)
                        HOLDER_CACHE.pop(token.mint_address, None)
                        continue

                    # Calculate price surge using the in-memory cache.
                    if token.mint_address in PRICE_CACHE and PRICE_CACHE[token.mint_address] > 0 and token.price is not None:
                        last_price = PRICE_CACHE[token.mint_address]
                        price_surge = ((token.price - last_price) / last_price) * 100
                    else:
                        price_surge = 0

                    # Calculate holders surge using the in-memory cache.
                    if token.mint_address in HOLDER_CACHE and token.holder is not None:
                        last_holder = HOLDER_CACHE[token.mint_address]
                        holders_surge = (token.holder - last_holder)
                    else:
                        holders_surge = 0

                    # Update the caches with current values.
                    PRICE_CACHE[token.mint_address] = token.price if token.price is not None else 0
                    HOLDER_CACHE[token.mint_address] = token.holder if token.holder is not None else 0

                    # Determine candidate status.
                    candidate_status = (price_surge >= 50 and holders_surge >= 10)

                    if candidate_status:
                        if not token.is_candidate and not token.is_notified:
                            token.is_candidate = True
                            token.is_notified = True
                            # Send Telegram notification (non-blocking).
                            loop = asyncio.get_running_loop()
                            await loop.run_in_executor(None, send_telegram_notification, token)
                        else:
                            token.is_candidate = True
                    else:
                        token.is_candidate = False
                        token.is_notified = False

                db.commit()
                print("Candidate analysis complete.")
        except Exception as e:
            print("Error during candidate analysis:", e)
        # Run every 5 minutes.
        await asyncio.sleep(300)


# -------------------------------
# Background Job: Liquidity Updates
# -------------------------------
async def update_liquidity():
    """
    Periodically updates the liquidity field for all tokens in the database by querying Raydium.
    """
    while True:
        try:
            with database.SessionLocal() as db:
                tokens = db.query(models.TokenMetadata).all()
                for token in tokens:
                    new_liquidity = get_dexscreener_data(token.mint_address)
                    token.liquidity = new_liquidity
                db.commit()
                print("Liquidity update complete.")
        except Exception as e:
            print("Error updating liquidity:", e)
        # Run every 10 minutes.
        await asyncio.sleep(600)



# -------------------------------
# Application Lifespan for Background Tasks
# -------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up...")
    # Start the Bitquery subscription loop.
    asyncio.create_task(bitquery_subscription_loop())
    # Start candidate analysis and liquidity update background jobs.
    asyncio.create_task(analyze_candidates())
    asyncio.create_task(update_liquidity())
    yield
    print("Shutting down...")

# Re-initialize FastAPI with the lifespan manager.
app = FastAPI(lifespan=lifespan)
