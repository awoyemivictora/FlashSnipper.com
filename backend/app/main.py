import json
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import asyncio
import websockets
import logging
from .routers import auth, sentiment, snipe, token, trade, user, util
from app.models import Trade, User, TokenMetadata
from app.database import AsyncSessionLocal, get_db
from app.security import get_current_user
from app.utils.dexscreener_api import get_dexscreener_data
from app.utils.raydium_apis import get_raydium_pool_info
from app.utils.rugcheck import check_rug
from app.utils.solscan_apis import get_solscan_token_meta, get_top_holders_info
from . import models, database
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from solana.rpc.async_api import AsyncClient
from solana.publickey import PublicKey


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load your environment variables and API keys.
load_dotenv()

PUMPPORTAL_WALLET_PUBLIC_KEY = os.getenv("PUMPPORTAL_WALLET_PUBLIC_KEY")
PUMPPORTAL_WALLET_PRIVATE_KEY = os.getenv("PUMPPORTAL_WALLET_PRIVATE_KEY")
PUMPPORTAL_API_KEY = os.getenv("PUMPPORTAL_API_KEY")

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "abc")
DEX_AGGREGATOR_API_HOST = os.getenv("DEX_AGGREGATOR_API_HOST")
SOLSCAN_API = os.getenv("SOLSCAN_API")

app = FastAPI(
    title="Solsniper API",
    description="A powerful Solana sniping bot with AI analysis and rug pull protection.",
    version="0.1.0",
)

# CORS Middleware (important for frontend communication)
origins = [
    "http://localhost:3000",  # Your React/Vite frontend development server
    "http://localhost:5173",  # Another common Vite dev port
    "http://localhost:8080",  # Additional common port
    # Add your production frontend URL(s) here
    # "https://yourproductionfrontend.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.include_router(api_router, prefix="/api/v1")
app.include_router(auth.router)
app.include_router(sentiment.router)
app.include_router(snipe.router)
# app.include_router(subscriptions.router, prefix="/subscriptions")
app.include_router(token.router)
app.include_router(trade.router)
app.include_router(user.router)
app.include_router(util.router)


# Database setup (ensure this is executed when the app starts)
# This creates tables based on your models.Base
@app.on_event("startup")
async def startup_event():
    async with database.async_engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    # Start the global token ingestion loop
    asyncio.create_task(pumpportal_subscription_loop_global())
    # Start the continuous metadata enrichment loop
    asyncio.create_task(metadata_enrichment_loop()) # <-- New task here
    logger.info("Database tables created and global background tasks started.")


#---- WebSocket Manager for Real-time Logs -----
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {} # {wallet_address: WebSocket}
        
        
    async def connect(self, websocket: WebSocket, wallet_address: str):
        await websocket.accept()
        self.active_connections[wallet_address] = websocket
        logger.info(f"WebSocket connected for wallet: {wallet_address}")
        
    
    def disconnect(self, wallet_address: str):
        if wallet_address in self.active_connections:
            del self.active_connections[wallet_address]
            logger.info(f"WebSocket disconnected for wallet: {wallet_address}")
            
    
    async def send_personal_message(self, message: str, wallet_address: str):
        if wallet_address in self.active_connections:
            try:
                await self.active_connections[wallet_address].send_text(message)
            except RuntimeError as e:
                logger.error(f"Error sending message to {wallet_address}: {e}")
                self.disconnect(wallet_address) # Disconnect if sending fails
                
    
    async def broadcast(self, message: str):
        # This might not be needed for per-user bots, but kept for general broadcast if required
        for connection in self.active_connections.values():
            await connection.send_text(message)
            

websocket_manager = ConnectionManager()



# Dictionary to keep track of active bot tasks per user
active_bot_tasks: Dict[str, asyncio.Task] = {}


# --- GLOBAL TOKEN INGESTION (Populates TokenMetadata for all users to check) ---
async def pumpportal_subscription_loop_global():
    """
    Runs the Pumpportal subscription continuously to ingest new tokens globally.
    This function ONLY populates the `TokenMetadata` table.
    User-specific bots will then query this table.
    """
    while True:
        try:
            uri = "wss://pumpportal.fun/api/data"
            async with websockets.connect(uri) as websocket:
                payload = {"method": "subscribeNewToken"}
                await websocket.send(json.dumps(payload))
                logger.info("Subscribed to Pumpportal new token events.")

                while True:
                    message = await websocket.recv()
                    event = json.loads(message)
                    logger.debug("Received Pumpportal event:", event) # Use debug to avoid spamming logs

                    if "mint" not in event:
                        continue # Skip non-token events

                    mint = event.get("mint")
                    if not mint or mint == "11111111111111111111111111111111":
                        logger.info("Skipping event due to missing or native null mint address.")
                        continue

                    # Process the token event by updating/creating its metadata
                    async with AsyncSessionLocal() as db_session:
                        try:
                            # Create or update a NewTokens entry (your existing logic)
                            token_trade = models.NewTokens( # Assuming models.NewTokens exists
                                mint_address=mint,
                                name=event.get("name"),
                                symbol=event.get("symbol"),
                                timestamp=datetime.utcnow(),
                                signature=event.get("signature"),
                                trader_public_key=event.get("traderPublicKey"),
                                tx_type=event.get("txType"),
                                initial_buy=event.get("initialBuy"),
                                sol_amount=event.get("solAmount"),
                                bonding_curve_key=event.get("bondingCurveKey"),
                                v_tokens_in_bonding_curve=event.get("vTokensInBonding_curve"),
                                v_sol_in_bonding_curve=event.get("vSolInBonding_curve"),
                                market_cap_sol=event.get("marketCapSol"),
                                uri=event.get("uri"),
                                pool=event.get("pool")
                            )
                            db_session.add(token_trade) # Use add or merge depending on if it's truly new or updateable
                            await db_session.commit()
                            logger.info(f"New token event recorded for: {mint}")
                            
                            # # --- We add 20 secs delay so that the metadata can populate on Dexscreener and Solscan API before we fetch them
                            # await asyncio.sleep(20)     # Wait for 20 seconds

                            # # Now, trigger metadata enrichment AFTER the delay
                            # await process_token_logic(mint, db_session)

                        except Exception as e:
                            logger.error(f"Error processing Pumpportal event {mint}: {e}")
                            await db_session.rollback()

        except websockets.exceptions.ConnectionClosedOK:
            logger.info("Pumpportal WebSocket connection closed normally. Reconnecting...")
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"Pumpportal WebSocket error: {e}. Reconnecting in 10 seconds...", exc_info=True)
            await asyncio.sleep(10)
        except Exception as e:
            logger.error(f"Unexpected error in Pumpportal subscription loop: {e}. Reconnecting in 30 seconds...", exc_info=True)
            await asyncio.sleep(30)




# --- CONTINUOUS METADATA ENRICHMENT LOOP ---
async def metadata_enrichment_loop():
    """
    Periodically fetches tokens from NewTokens and enriches/updates their metadata
    in TokenMetadata. This runs in a separate background task.
    """
    logger.info("Starting continuous metadata enrichment loop.")
    while True:
        try:
            async with AsyncSessionLocal() as db:
                # Select tokens from NewTokens that might need metadata.
                # Criteria:
                # 1. Newly added (check timestamp from NewTokens)
                # 2. Existing tokens in TokenMetadata that are missing key info (e.g., pair_address, market_cap)
                # 3. Existing tokens that haven't been checked recently (`last_checked_at` in TokenMetadata)

                # For simplicity, let's target tokens from `NewTokens` that haven't been fully processed
                # or need a retry. A robust solution might involve a `status` field on `NewTokens`
                # like 'pending_metadata', 'metadata_fetched', 'failed_metadata'.

                # Let's start by processing all new tokens and refreshing existing ones.
                # Fetching tokens from NewTokens table that are relatively recent
                # and haven't been successfully processed or need a refresh.
                
                # Option A: Get all NewTokens and check if they exist/are complete in TokenMetadata
                # This might be too broad if NewTokens grows very large.
                # Better: Join with TokenMetadata and find gaps/old data.

                # Let's fetch all unique mint addresses from NewTokens,
                # then check their status in TokenMetadata.
                stmt = select(
                    models.NewTokens.mint_address,
                    models.NewTokens.timestamp # <-- Include timestamp here
                ).distinct().order_by(models.NewTokens.timestamp.desc())

                result = await db.execute(stmt)
                # Now, each row in result will be a tuple: (mint_address, timestamp)
                # We only need the mint_address for our list, but we had to select timestamp for ordering
                mint_addresses_to_process = [row.mint_address for row in result.all()] # Use .all() to get all rows as tuples
                
                # Fetch existing TokenMetadata for these mints to check status
                stmt_meta = select(models.TokenMetadata).where(
                    models.TokenMetadata.mint_address.in_(mint_addresses_to_process)
                )
                result_meta = await db.execute(stmt_meta)
                existing_metadata = {t.mint_address: t for t in result_meta.scalars().all()}

                # Logic to determine which tokens need processing
                mints_for_enrichment = []
                for mint in mint_addresses_to_process:
                    token_meta = existing_metadata.get(mint)
                    
                    # If token_meta does not exist (new token to TokenMetadata)
                    # OR if it exists but is missing critical data (e.g., pair_address from dexscreener)
                    # OR if it hasn't been checked recently (e.g., within the last 5 minutes)
                    if not token_meta: # Token is in NewTokens but not yet in TokenMetadata
                        mints_for_enrichment.append(mint)
                    elif not token_meta.pair_address or not token_meta.market_cap: # Missing crucial Dexscreener data
                        mints_for_enrichment.append(mint)
                    elif token_meta.last_checked_at and (datetime.utcnow() - token_meta.last_checked_at) > timedelta(minutes=5):
                        # Re-check tokens older than 5 minutes to get updated data
                        mints_for_enrichment.append(mint)
                    # Add more specific checks here based on what data is commonly missing

                if mints_for_enrichment:
                    logger.info(f"Found {len(mints_for_enrichment)} tokens needing metadata enrichment. Processing...")
                    for mint in mints_for_enrichment:
                        await process_token_logic(mint, db)
                        # Introduce a small delay between each API call to avoid rate limits
                        await asyncio.sleep(5) 
                else:
                    logger.info("No new or un-enriched tokens found for metadata processing.")

        except Exception as e:
            logger.error(f"Error in metadata enrichment loop: {e}", exc_info=True)
            
        # Define how often the enrichment loop runs
        await asyncio.sleep(20) # Check for new/missing metadata every 20 seconds






# --- TOKEN METADATA ENRICHMENT (Called by global ingestion loop) ---
async def process_token_logic(mint: str, db: AsyncSession):
    """
    Enhanced token processing with Dexscreener, Solscan, and Raydium data,
    updating relevant fields in the TokenMetadata model.
    This function is called by the global ingestion loop and by user-specific bot loops
    to ensure token data is always fresh.
    """
    try:
        logger.info(f"Processing token metadata for: {mint}")

        # Fetch existing token or create a new one
        stmt = select(TokenMetadata).where(TokenMetadata.mint_address == mint)
        result = await db.execute(stmt)
        token = result.scalars().first()
        if not token:
            token = TokenMetadata(mint_address=mint)
            db.add(token) # Add to session if new

        # --- Dexscreener Data ---
        dex_data = await get_dexscreener_data(mint)
        if dex_data:
            token.dexscreener_url = dex_data.get("dexscreener_url")
            token.pair_address = dex_data.get("pair_address")
            token.price_native = dex_data.get("price_native")
            token.price_usd = dex_data.get("price_usd")
            token.market_cap = dex_data.get("market_cap")
            token.pair_created_at = dex_data.get("pair_created_at")
            token.websites = dex_data.get("websites")
            token.twitter = dex_data.get("twitter")
            token.telegram = dex_data.get("telegram")
            token.token_name = dex_data.get("token_name")
            token.token_symbol = dex_data.get("token_symbol")
            token.dex_id = dex_data.get("dex_id")
            token.volume_h24 = dex_data.get("volume_h24")
            token.volume_h6 = dex_data.get("volume_h6")
            token.volume_h1 = dex_data.get("volume_h1")
            token.volume_m5 = dex_data.get("volume_m5")
            token.price_change_h1 = dex_data.get("price_change_h1")
            token.price_change_m5 = dex_data.get("price_change_m5")
            token.price_change_h6 = dex_data.get("price_change_h6")
            token.price_change_h24 = dex_data.get("price_change_h24")

            # Update Basic Filter: Socials Added
            token.socials_present = (
                dex_data.get("twitter") not in [None, "N/A"] or
                dex_data.get("telegram") not in [None, "N/A"] or
                (dex_data.get("websites") is not None and len(dex_data["websites"]) > 0)
            )

            # Update Basic Filter: Pump.fun Migrated
            # A more robust check might involve checking for a specific 'DEX' field if Dexscreener provides it.
            token.migrated_from_pumpfun = "pump.fun" in dex_data.get("dex_id", "").lower() and "raydium" in dex_data.get("dex_id", "").lower()

        # --- Raydium Pool Info ---
        if token.pair_address:
            raydium_data = await get_raydium_pool_info(token.pair_address)
            if raydium_data:
                token.liquidity_burnt = raydium_data.get("burnPercent", 0) == 100
                token.liquidity_pool_size_sol = raydium_data.get("tvl") # Assuming TVL is in USD for now, convert if your field is SOL
                # TODO: If `liquidity_pool_size_sol` MUST be in SOL, fetch SOL price and convert `tvl`.

        # --- Solscan Token Metadata ---
        solscan_data = await get_solscan_token_meta(mint)
        if solscan_data:
            token.immutable_metadata = solscan_data.get("is_mutable") is False
            token.mint_authority_renounced = solscan_data.get("mint_authority") is None
            token.freeze_authority_revoked = solscan_data.get("freeze_authority") is None
            token.token_decimals = solscan_data.get("decimals")
            # Solscan data also provides holder count directly
            token.holder = solscan_data.get("holder")


        # --- Top 10 Holders Percentage ---
        top10_percentage = await get_top_holders_info(mint)
        token.top10_holders_percentage = top10_percentage

        token.last_checked_at = datetime.utcnow()

        await db.merge(token)
        await db.commit()

        logger.info(f"Successfully processed and updated token data for: {mint}")

    except httpx.HTTPError as e:
        logger.error(f"HTTP error while processing token {mint}: {e}")
        await db.rollback()
    except Exception as ex:
        logger.error(f"Unexpected error while processing token {mint}: {ex}")
        await db.rollback()





























#============================ ALL ENDPOINTS STARTS HERE ========================
@app.get("/ping")
async def ping():
    """
    Health check endpoint.
    """
    logger.info("Ping received.")
    return {"message": "pong", "status": "ok"}


@app.get("/health")
async def health_check():
    """
    Detailed health check including database and external API reachability.
    (Placeholder for now, implement actual checks)
    """
    # TODO: Add actual checks for DB connection, Solana RPC, external APIs
    db_status = "ok"
    solana_rpc_status = "ok"
    dexscreener_api_status = "ok"
    
    logger.info("Health check performed.")
    return {
        "status": "healthy",
        "database": db_status,
        "solana_rpc": solana_rpc_status,
        "dexscreener_api": dexscreener_api_status,
        "message": "All essential services are operational."
    }
    
@app.post("/user/update-rpc")
async def update_user_rpc(
    rpc_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not current_user.is_premium:
        raise HTTPException(status_code=403, detail="Custom RPC is available only for premium users.")
    
    # Validate RPC URLs
    https_url = rpc_data.get("https")
    wss_url = rpc_data.get("wss")
    if https_url and not https_url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Invalid HTTPS RPC URL")
    if wss_url and not wss_url.startswith("wss://"):
        raise HTTPException(status_code=400, detail="Invalid WSS RPC URL")
    
    current_user.custom_rpc_https = https_url
    current_user.custom_rpc_wss = wss_url
    await db.merge(current_user)
    await db.commit()
    return {"status": "Custom RPC settings updated."}


#--- WebSocket Endpoint for Real-time Logs ----
@app.websocket("/ws/logs/{wallet_address}")
async def websocket_endpoint(websocket: WebSocket, wallet_address: str, db: AsyncSession = Depends(get_db)):
    # For simplicity, we'll allow connection by wallet address.
    
    await websocket_manager.connect(websocket, wallet_address)
    try:
        while True:
            # Keep the connection alieve, wait for messages (optional, can be empty)
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(wallet_address)
    except Exception as e:
        logger.error(f"WebSocket error for {wallet_address}: {e}")
        websocket_manager.disconnect(wallet_address)
        


@app.get("/wallet/balance/{wallet_address}")
async def get_wallet_balance(wallet_address: str):
    try:
        async with AsyncClient(settings.SOLANA_RPC_URL) as client:
            pubkey = PublicKey(wallet_address)
            balance_response = await client.get_balance(pubkey)
            lamports = balance_response['result']['value']
            sol_balance = lamports / 1_000_000_000
            return {"wallet_address": wallet_address, "sol_balance": sol_balance}
    except Exception as e:
        logger.error(f"Error fetching balance for {wallet_address}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching balance: {str(e)}")


@app.post("/bot/start")
async def start_user_bot(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Check minimum balance (0.3 SOL)
    async with AsyncClient(settings.SOLANA_RPC_URL) as client:
        pubkey = PublicKey(current_user.wallet_address)
        balance_response = await client.get_balance(pubkey)
        sol_balance = balance_response['result']['value'] / 1_000_000_000
        if sol_balance < 0.3:
            raise HTTPException(status_code=400, detail="Wallet balance must be at least 0.3 SOL to start the bot.")

    if current_user.wallet_address in active_bot_tasks:
        raise HTTPException(status_code=400, detail="Bot already running for this user.")

    task = asyncio.create_task(run_user_specific_bot_loop(current_user.wallet_address))
    active_bot_tasks[current_user.wallet_address] = task
    logger.info(f"Bot started for user: {current_user.wallet_address}")
    await websocket_manager.send_personal_message(
        json.dumps({"type": "log", "message": "Bot started successfully!", "status": "info"}),
        current_user.wallet_address
    )
    return {"status": "Bot started for user wallet."}


# Endpoint to stop the bot from the frontend by the user
@app.post("/bot/stop")
async def stop_user_bot(current_user: User = Depends(get_current_user)):
    if current_user.wallet_address in active_bot_tasks:
        task = active_bot_tasks[current_user.wallet_address]
        task.cancel() # Request the task to cancel
        # The `finally` block in `run_user_specific_bot_loop` will clean up `active_bot_tasks`
        await websocket_manager.send_personal_message(
            json.dumps({"type": "log", "message": "Bot stop requested. It will stop shortly.", "status": "info"}),
            current_user.wallet_address
        )
        return {"status": "Bot stop requested."}
    else:
        raise HTTPException(status_code=400, detail="No bot running for this user.")


@app.post("/trade/log-trade")
async def log_trade(
    trade_data: LogTradeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    fee_percentage = 0.01
    fee_sol = trade_data.amount_sol * fee_percentage if trade_data.amount_sol else 0
    amount_after_fee = trade_data.amount_sol - fee_sol if trade_data.amount_sol else 0
    
    trade = Trade(
        user_wallet_address=current_user.wallet_address,
        mint_address=trade_data.mint_address,
        token_symbol=trade_data.token_symbol,
        trade_type=trade_data.trade_type,
        amount_sol=amount_after_fee,
        amount_tokens=trade_data.amount_tokens,
        price_sol_per_token=trade_data.price_sol_per_token,
        price_usd_at_trade=trade_data.price_usd_at_trade,
        buy_tx_hash=trade_data.tx_hash if trade_data.trade_type == "buy" else None,
        sell_tx_hash=trade_data.tx_hash if trade_data.trade_type == "sell" else None,
        profit_usd=trade_data.profit_usd,
        profit_sol=trade_data.profit_sol,
        log_message=trade_data.log_message,
        buy_price=trade_data.buy_price,
        entry_price=trade_data.entry_price,
        stop_loss=trade_data.stop_loss,
        take_profit=trade_data.take_profit,
        token_amounts_purchased=trade_data.token_amounts_purchased,
        token_decimals=trade_data.token_decimals,
        sell_reason=trade_data.sell_reason,
        swap_provider=trade_data.swap_provider
    )
    db.add(trade)
    await db.commit()
    
    await websocket_manager.send_personal_message(
        json.dumps({"type": "log", "message": f"Applied 1% fee ({fee_sol:.6f} SOL) on {trade_data.trade_type} trade.", "status": "info"}),
        current_user.wallet_address
    )
    return {"status": "Trade logged successfully."}

@app.get("/trade/history")
async def get_trade_history(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(Trade).filter(Trade.user_wallet_address == current_user.wallet_address).order_by(Trade.buy_timestamp.desc())
    result = await db.execute(stmt)
    trades = result.scalars().all()
    return [TradeLog(**trade.__dict__) for trade in trades]


@app.post("/subscribe/premium")
async def subscribe_premium(
    subscription_data: SubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        subscription = stripe.Subscription.create(
            customer={"email": subscription_data.email},
            items=[{"price": settings.STRIPE_PREMIUM_PRICE_ID}],  # Add STRIPE_PREMIUM_PRICE_ID to settings.py
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"]
        )
        
        sub = Subscription(
            user_wallet_address=current_user.wallet_address,
            plan_name="Premium",
            payment_provider_id=subscription.id,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30)
        )
        current_user.is_premium = True
        current_user.premium_start_date = datetime.utcnow()
        current_user.premium_end_date = datetime.utcnow() + timedelta(days=30)
        
        db.add(sub)
        await db.merge(current_user)
        await db.commit()
        return {"status": "Premium subscription activated", "payment_intent": subscription.latest_invoice.payment_intent}
    except Exception as e:
        logger.error(f"Subscription failed: {e}")
        raise HTTPException(status_code=400, detail=f"Subscription failed: {str(e)}")
    
    

# THE MAIN BOT LOOP PER USER
async def run_user_specific_bot_loop(user_wallet_address: str):
    """
    Main loop for a user-specific bot.
    It fetches tokens from the DB (populated by global Pumpportal listener),
    applies user's filters, and orchestrates trades via frontend instructions.
    """
    logger.info(f"Starting user-specific bot loop for {user_wallet_address}")
    try:
        while True:
            async with AsyncSessionLocal() as db:
                user_result = await db.execute(select(User).filter(User.wallet_address == user_wallet_address))
                user = user_result.scalar_one_or_none()

                if not user:
                    logger.warning(f"User {user_wallet_address} not found, stopping bot loop.")
                    await websocket_manager.send_personal_message(
                        json.dumps({"type": "log", "message": "User session expired or wallet removed. Stopping bot.", "status": "error"}),
                        user_wallet_address
                    )
                    break # Exit the loop

                # Check if the user has premium access settings for filters
                is_premium_user = user.is_premium

                # 1. Fetch new token candidates from the TokenMetadata table
                # We need a strategy to decide which tokens to look at.
                # Options:
                # A) Look for tokens that are new and haven't been 'analyzed_for_user' yet.
                # B) Look for tokens that have been recently updated.
                # C) Only consider tokens posted after the user started their bot session (more complex)
                
                # For simplicity, let's fetch recently updated tokens that haven't been bought by this user.
                # You might add a field like `analyzed_for_users: JSON` to TokenMetadata
                # to track which users have already evaluated a token, or a `user_trades` table
                # to see if a token was already traded by *this specific user*.

                # For now, let's fetch tokens that are recently checked (meaning their metadata is fresh)
                # and haven't been marked as `is_bought` for *this user's trade history*.
                # This implies a `Trade` table or a per-user `TokenMetadata` status.
                # Assuming `TokenMetadata` can somehow track user-specific `is_bought` status
                # (which is not in current `TokenMetadata` model).
                # A proper solution would require a `UserTrade` or `UserTokenStatus` table.

                # Let's adjust for simplicity: fetch newly added tokens in the last hour
                # that have not yet been "seen" or processed for this specific user.
                # This requires a more complex join or a new field on TokenMetadata.
                
                # For now, let's fetch tokens whose metadata has been recently updated by the global loop
                # and assume we only process them once per user per significant update.
                
                # A better approach for user-specific bot:
                # Have a `UserBotLog` or `UserTokenEvaluation` table:
                # `user_wallet_address`, `mint_address`, `evaluated_at`, `passed_filters_at`, `buy_attempted_at` etc.
                # This loop then queries for tokens that *this user* hasn't yet processed.

                # Simplified example: just fetch a few *random* tokens as candidates for processing
                # In a real bot, you'd have a more intelligent queue/discovery mechanism.
                # We need to ensure we don't re-evaluate the same token endlessly for the same user.
                
                # Let's assume for now that we will process *all* tokens in TokenMetadata
                # and `apply_user_filters` will handle if the user has already bought it.
                # (This is less efficient for many tokens/users, but demonstrates logic).

                # Fetch tokens that have been recently processed by the global loop
                # and are potentially new candidates for *any* user.
                # Add a filter to prevent processing tokens that are too old or too new,
                # if that's a user setting, or a general bot strategy.
                
                # Fetching tokens updated in the last X minutes (e.g., 30 minutes)
                recent_time_threshold = datetime.utcnow() - timedelta(minutes=30)
                stmt = select(TokenMetadata).filter(
                    TokenMetadata.updated_at >= recent_time_threshold
                ).order_by(TokenMetadata.updated_at.desc()).limit(10) # Limit for efficiency
                
                result = await db.execute(stmt)
                potential_candidates = result.scalars().all()

                for token_meta in potential_candidates:
                    # Check if this specific user has already traded this token
                    # This requires a `Trade` model with `user_wallet_address` and `mint_address`
                    user_trade_exists_stmt = select(models.Trade).filter(
                        models.Trade.user_wallet_address == user_wallet_address,
                        models.Trade.mint_address == token_meta.mint_address
                    )
                    user_trade_result = await db.execute(user_trade_exists_stmt)
                    if user_trade_result.scalar_one_or_none():
                        logger.debug(f"User {user_wallet_address} already traded {token_meta.mint_address}. Skipping.")
                        continue # Skip if user already traded this token

                    # Apply user-specific filters
                    passes_all_filters = await apply_user_filters(user, token_meta, db, websocket_manager)

                    if not passes_all_filters:
                        log_msg = (f"Skipping {token_meta.token_symbol} ({token_meta.mint_address}) "
                                   f"for {user_wallet_address}: Did not pass user-specific filters.")
                        logger.info(log_msg)
                        await websocket_manager.send_personal_message(
                            json.dumps({"type": "log", "message": log_msg, "status": "info"}),
                            user_wallet_address
                        )
                        continue

                    # If filters pass, attempt to buy
                    log_msg = (f"Filters passed for {token_meta.token_symbol} ({token_meta.mint_address}) "
                               f"for {user_wallet_address}. Attempting buy instruction...")
                    logger.info(log_msg)
                    await websocket_manager.send_personal_message(
                        json.dumps({"type": "log", "message": log_msg, "status": "info"}),
                        user_wallet_address
                    )

                    # Send BUY instruction to frontend
                    await execute_user_trade(
                        user_wallet_address=user_wallet_address,
                        mint_address=token_meta.mint_address,
                        amount_sol=user.buy_amount_sol, # From user's settings
                        trade_type="buy",
                        slippage=user.slippage_bps / 100.0, # Convert basis points to percentage
                        take_profit=user.take_profit_percentage,
                        stop_loss=user.stop_loss_percentage,
                        db=db, # Pass db for potential future logging/updates
                        websocket_manager=websocket_manager
                    )
                    # Once a buy instruction is sent, we might want to mark this token as "pending buy"
                    # for this user to avoid re-sending. This needs a new field or a UserTrade entry.
                    # For simplicity, in this loop, it will just continue.
                    
                    # To mimic SolSniper, after a successful buy (frontend confirms and logs trade),
                    # the bot will usually then monitor *that specific trade* for sell conditions.
                    # This monitoring would likely be a separate asyncio task per trade, or integrated
                    # into a sophisticated main loop that tracks active trades for each user.

                    # For now, let's just break after sending a buy instruction for one token,
                    # so the bot doesn't spam buys for every eligible token in one loop cycle.
                    # In a real bot, you'd likely remove this break and manage concurrency.
                    # break # Remove this for continuous evaluation if needed

            # Define how often a user's bot loop re-evaluates tokens
            await asyncio.sleep(user.bot_check_interval_seconds or 10) # User can configure interval

    except asyncio.CancelledError:
        logger.info(f"Bot task for {user_wallet_address} cancelled.")
    except Exception as e:
        logger.error(f"Error in user bot loop for {user_wallet_address}: {e}", exc_info=True)
        await websocket_manager.send_personal_message(
            json.dumps({"type": "log", "message": f"Bot encountered a critical error: {e}", "status": "critical"}),
            user_wallet_address
        )
    finally:
        if user_wallet_address in active_bot_tasks:
            del active_bot_tasks[user_wallet_address]
        logger.info(f"User-specific bot loop for {user_wallet_address} ended.")



# --- Helper function to apply user-specific filters ---
async def apply_user_filters(user: User, token_meta: TokenMetadata, db: AsyncSession, websocket_manager: ConnectionManager) -> bool:
    async def log_failure(filter_name: str):
        logger.debug(f"Token {token_meta.mint_address} failed {filter_name} for user {user.wallet_address}.")
        await websocket_manager.send_personal_message(
            json.dumps({"type": "log", "message": f"Token {token_meta.token_symbol or token_meta.mint_address} failed {filter_name} filter.", "status": "info"}),
            user.wallet_address
        )

    # Basic Filters
    if user.filter_socials_added and not token_meta.socials_present:
        await log_failure("Socials Added")
        return False
    if user.filter_liquidity_burnt and not token_meta.liquidity_burnt:
        await log_failure("Liquidity Burnt")
        return False
    if user.filter_immutable_metadata and not token_meta.immutable_metadata:
        await log_failure("Immutable Metadata")
        return False
    if user.filter_mint_authority_renounced and not token_meta.mint_authority_renounced:
        await log_failure("Mint Authority Renounced")
        return False
    if user.filter_freeze_authority_revoked and not token_meta.freeze_authority_revoked:
        await log_failure("Freeze Authority Revoked")
        return False
    if user.filter_pump_fun_migrated and not token_meta.migrated_from_pumpfun:
        await log_failure("Pump.fun Migrated")
        return False
    if user.filter_check_pool_size_min_sol and (token_meta.liquidity_pool_size_sol is None or token_meta.liquidity_pool_size_sol < user.filter_check_pool_size_min_sol):
        await log_failure(f"Insufficient Liquidity Pool Size (min {user.filter_check_pool_size_min_sol} SOL)")
        return False

    # General Checks
    if token_meta.pair_created_at:
        deployed_time = datetime.utcfromtimestamp(token_meta.pair_created_at)
        age = datetime.utcnow() - deployed_time
        if age < timedelta(minutes=15) or age > timedelta(hours=72):
            await log_failure("Token Age (15m-72h)")
            return False
    else:
        await log_failure("Missing Pair Creation Time")
        return False

    if token_meta.market_cap is None or float(token_meta.market_cap) < 30000:
        await log_failure("Market Cap (< $30k)")
        return False

    if token_meta.holder is None or token_meta.holder < 20:
        await log_failure("Holder Count (< 20)")
        return False

    rug_data = await check_rug(token_meta.mint_address)
    if not (rug_data and "score" in rug_data and rug_data["score"] < 100):
        await log_failure("RugCheck Score (>= 100)")
        return False

    # Premium Filters
    if user.is_premium:
        if user.filter_top_holders_max_pct and token_meta.top10_holders_percentage and token_meta.top10_holders_percentage > user.filter_top_holders_max_pct:
            await log_failure(f"Top 10 Holders % (>{user.filter_top_holders_max_pct}%)")
            return False
        
        # Placeholder for Bundled Max (requires mempool analysis)
        if user.filter_bundled_max:
            # TODO: Implement mempool analysis or use Solscan heuristics
            pass
        
        # Placeholder for Max Same Block Buys (requires mempool analysis)
        if user.filter_max_same_block_buys:
            # TODO: Implement mempool analysis or use Solscan heuristics
            pass
        
        if user.filter_safety_check_period_seconds and token_meta.pair_created_at:
            required_age = timedelta(seconds=user.filter_safety_check_period_seconds)
            current_age = datetime.utcnow() - datetime.utcfromtimestamp(token_meta.pair_created_at)
            if current_age < required_age:
                await log_failure(f"Safety Check Period (<{user.filter_safety_check_period_seconds}s)")
                return False

    return True



# Helper funtion for the bot to execute the trade per user's wallet's settings from the frontend
async def execute_user_trade(
    user_wallet_address: str,
    mint_address: str,
    amount_sol: float,
    trade_type: str,
    slippage: float,
    take_profit: Optional[float],
    stop_loss: Optional[float],
    timeout_seconds: Optional[int],
    trailing_stop_loss_pct: Optional[float],
    db: AsyncSession,
    websocket_manager: ConnectionManager
):
    user_stmt = select(User).filter(User.wallet_address == user_wallet_address)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()
    
    rpc_url = user.custom_rpc_https if user.is_premium and user.custom_rpc_https else settings.SOLANA_RPC_URL
    wss_url = user.custom_rpc_wss if user.is_premium and user.custom_rpc_wss else settings.SOLANA_WEBSOCKET_URL
    
    trade_instruction_message = {
        "type": "trade_instruction",
        "trade_type": trade_type,
        "mint_address": mint_address,
        "amount_sol": amount_sol,
        "slippage": slippage,
        "take_profit": take_profit,
        "stop_loss": stop_loss,
        "timeout_seconds": timeout_seconds,
        "trailing_stop_loss_pct": trailing_stop_loss_pct,
        "rpc_url": rpc_url,
        "wss_url": wss_url,
        "message": f"Please execute a {trade_type} trade for {mint_address}."
    }
    await websocket_manager.send_personal_message(
        json.dumps(trade_instruction_message),
        user_wallet_address
    )
    
    if trade_type == "buy":
        asyncio.create_task(monitor_trade_for_sell(
            user_wallet_address, mint_address, take_profit, stop_loss, timeout_seconds, trailing_stop_loss_pct, db, websocket_manager
        ))

async def monitor_trade_for_sell(
    user_wallet_address: str,
    mint_address: str,
    take_profit: Optional[float],
    stop_loss: Optional[float],
    timeout_seconds: Optional[int],
    trailing_stop_loss_pct: Optional[float],
    db: AsyncSession,
    websocket_manager: ConnectionManager
):
    logger.info(f"Monitoring trade for {user_wallet_address} on {mint_address}")
    start_time = datetime.utcnow()
    highest_price = None
    
    while True:
        try:
            dex_data = await get_dexscreener_data(mint_address)
            if not dex_data:
                await websocket_manager.send_personal_message(
                    json.dumps({"type": "log", "message": f"Failed to fetch price for {mint_address}. Retrying...", "status": "error"}),
                    user_wallet_address
                )
                await asyncio.sleep(10)
                continue
            
            current_price = float(dex_data.get("price_usd", 0))
            trade_stmt = select(Trade).filter(
                Trade.user_wallet_address == user_wallet_address,
                Trade.mint_address == mint_address,
                Trade.trade_type == "buy"
            ).order_by(Trade.buy_timestamp.desc())
            trade_result = await db.execute(trade_stmt)
            trade = trade_result.scalar_one_or_none()
            
            if not trade:
                logger.error(f"No buy trade found for {user_wallet_address} and {mint_address}")
                break
            
            buy_price = trade.price_usd_at_trade or 0
            
            # Check timeout
            if timeout_seconds and (datetime.utcnow() - start_time).total_seconds() > timeout_seconds:
                await execute_user_trade(
                    user_wallet_address, mint_address, trade.amount_tokens, "sell", 0.05, None, None, None, None, db, websocket_manager
                )
                await websocket_manager.send_personal_message(
                    json.dumps({"type": "log", "message": f"Selling {mint_address} due to timeout.", "status": "info"}),
                    user_wallet_address
                )
                break
            
            # Update trailing stop-loss
            if trailing_stop_loss_pct and current_price > (highest_price or buy_price):
                highest_price = current_price
                stop_loss = highest_price * (1 - trailing_stop_loss_pct / 100)
            
            # Check take-profit
            if take_profit and current_price >= buy_price * (1 + take_profit / 100):
                await execute_user_trade(
                    user_wallet_address, mint_address, trade.amount_tokens, "sell", 0.05, None, None, None, None, db, websocket_manager
                )
                await websocket_manager.send_personal_message(
                    json.dumps({"type": "log", "message": f"Selling {mint_address} at take-profit.", "status": "info"}),
                    user_wallet_address
                )
                break
            
            # Check stop-loss
            if stop_loss and current_price <= buy_price * (1 - stop_loss / 100):
                await execute_user_trade(
                    user_wallet_address, mint_address, trade.amount_tokens, "sell", 0.05, None, None, None, None, db, websocket_manager
                )
                await websocket_manager.send_personal_message(
                    json.dumps({"type": "log", "message": f"Selling {mint_address} at stop-loss.", "status": "info"}),
                    user_wallet_address
                )
                break
            
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Error monitoring trade for {mint_address}: {e}")
            await websocket_manager.send_personal_message(
                json.dumps({"type": "log", "message": f"Error monitoring {mint_address}: {str(e)}", "status": "error"}),
                user_wallet_address
            )
            await asyncio.sleep(10)





