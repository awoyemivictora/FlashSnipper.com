
  
  
# import logging
# import os
# from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Request, Response
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from contextlib import asynccontextmanager
# import json
# import asyncio
# import traceback
# from typing import Dict, Optional
# from datetime import datetime, timedelta
# import grpc
# import base58
# import base64
# from sqlalchemy import delete, or_, select
# from sqlalchemy.ext.asyncio import AsyncSession
# from dotenv import load_dotenv
# import aiohttp
# from tenacity import retry, stop_after_attempt, wait_exponential
# from solders.pubkey import Pubkey
# from solders.keypair import Keypair
# from solders.transaction import VersionedTransaction
# from solana.rpc.async_api import AsyncClient
# from jupiter_python_sdk.jupiter import Jupiter
# from app.dependencies import get_current_user_by_wallet
# from app.models import Subscription, TokenMetadataArchive, Trade, User, TokenMetadata, NewTokens
# from app.database import AsyncSessionLocal, get_db
# from app.schemas import LogTradeRequest, SubscriptionRequest
# from app.utils.profitability_engine import engine as profitability_engine
# from app.utils.dexscreener_api import get_dexscreener_data
# from app.utils.webacy_api import check_webacy_risk
# from app import models, database
# from app.config import settings
# from app.security import decrypt_private_key_backend
# import redis.asyncio as redis
# from app.utils.bot_components import ConnectionManager, execute_jupiter_swap, execute_user_buy, websocket_manager

# # Add generated stubs
# import sys
# sys.path.append('app/generated')
# from app.generated.geyser_pb2 import SubscribeRequest, GetVersionRequest, CommitmentLevel
# from app.generated.geyser_pb2_grpc import GeyserStub

# # Disable SQLAlchemy logging
# logging.config.dictConfig({
#     'version': 1,
#     'disable_existing_loggers': False,
#     'loggers': {
#         'sqlalchemy.engine': {'level': 'ERROR', 'handlers': [], 'propagate': False},
#         'sqlalchemy.pool': {'level': 'ERROR', 'handlers': [], 'propagate': False},
#         'sqlalchemy.dialects': {'level': 'ERROR', 'handlers': [], 'propagate': False},
#     }
# })

# # Load environment variables
# load_dotenv()

# # Configure logger
# logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)
# if not logger.handlers:
#     handler = logging.StreamHandler()
#     handler.setLevel(logging.INFO)
#     formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     handler.setFormatter(formatter)
#     logger.addHandler(handler)
#     logger.propagate = False

# # Redis client
# redis_client = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379, db=0)

# # FastAPI app
# app = FastAPI(
#     title="Solsniper API",
#     description="A powerful Solana sniping bot with AI analysis and rug pull protection.",
#     version="0.2.0",
# )

# # CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # DEV ONLY
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Import routers AFTER app creation to avoid circular imports
# from app.routers import auth, token, trade, user, util

# # Include routers
# app.include_router(auth.router)
# app.include_router(token.router)
# app.include_router(trade.router)
# app.include_router(user.router)
# app.include_router(util.router)

# # Active bot tasks
# active_bot_tasks: Dict[str, asyncio.Task] = {}

# # ===================================================================
# # HYPER SNIPER 2025 — INSTANT SNIPE ENGINE (NO DELAY, NO FILTERS)
# # ===================================================================

# async def instant_snipe_on_pool_creation(mint_address: str, pool_data: dict):
#     """
#     Called IMMEDIATELY when a new Raydium pool is detected.
#     Buys for ALL connected users within 3 seconds.
#     Sells automatically after 15-25 seconds.
#     No filters. No data fetching. No mercy.
#     """
#     logger.info(f"🚀 HYPER SNIPE ACTIVATED → {mint_address[:8]} | INSTANT BUY INITIATED")
    
#     # Create minimal token record so buy function works
#     async with AsyncSessionLocal() as db:
#         # Check if token already exists
#         existing_token = await db.execute(
#             select(TokenMetadata).where(TokenMetadata.mint_address == mint_address)
#         )
#         token = existing_token.scalar_one_or_none()
        
#         if not token:
#             token = TokenMetadata(
#                 mint_address=mint_address,
#                 token_symbol="SNIPING",
#                 token_name="Hyper Snipe",
#                 trading_recommendation="INSTANT_BUY",
#                 profitability_score=100.0,
#                 profitability_confidence=100.0,
#                 last_checked_at=datetime.utcnow(),
#                 pair_created_at=int(datetime.utcnow().timestamp()),
#                 liquidity_pool_size_sol=10.0,  # Default to pass filters
#                 socials_present=True  # Default to pass filters
#             )
#             db.add(token)
#             await db.commit()
#         else:
#             # Update existing token for instant buy
#             token.trading_recommendation = "INSTANT_BUY"
#             token.last_checked_at = datetime.utcnow()
#             await db.commit()

#     # Get all currently connected users
#     connected_wallets = list(websocket_manager.active_connections.keys())

#     if not connected_wallets:
#         logger.info("No users connected → skipping snipe")
#         return

#     logger.info(f"🔥 Sniping {mint_address[:8]} for {len(connected_wallets)} user(s) NOW!")

#     buy_tasks = []
#     for wallet_address in connected_wallets:
#         # Prevent duplicate snipes
#         lock_key = f"snipe_lock:{wallet_address}:{mint_address}"
#         if await redis_client.get(lock_key):
#             continue
#         await redis_client.setex(lock_key, 30, "1")  # 30s lock

#         # Trigger buy
#         buy_tasks.append(
#             trigger_instant_buy_for_user(wallet_address, mint_address, token)
#         )

#     # Fire all buys in parallel - MAXIMUM SPEED
#     await asyncio.gather(*buy_tasks, return_exceptions=True)


# async def trigger_instant_buy_for_user(wallet_address: str, mint_address: str, token: TokenMetadata):
#     """Execute buy + schedule auto-sell in 15-25 seconds"""
#     async with AsyncSessionLocal() as db:
#         user = (await db.execute(
#             select(User).where(User.wallet_address == wallet_address)
#         )).scalar_one_or_none()

#         if not user:
#             return

#         # Prevent double buy
#         exists = await db.execute(select(Trade).where(
#             Trade.user_wallet_address == wallet_address,
#             Trade.mint_address == mint_address,
#             Trade.sell_timestamp.is_(None)
#         ))
#         if exists.scalar_one_or_none():
#             return

#         logger.info(f"⚡ BUY → {wallet_address[:6]} sniping {mint_address[:8]}")

#         try:
#             # Execute instant buy (bypass all filters)
#             await execute_hyper_buy(user, token, db)

#             # Random sell time between 15-25 seconds for variation
#             sell_delay = 15 + (hash(wallet_address + mint_address) % 11)  # 15-25 seconds
#             logger.info(f"⏰ Auto-sell scheduled in {sell_delay}s for {wallet_address[:6]}")

#             # Schedule auto-sell
#             asyncio.create_task(auto_sell_after_delay(user, mint_address, sell_delay))

#             await websocket_manager.send_personal_message(json.dumps({
#                 "type": "log",
#                 "log_type": "success",
#                 "message": f"🔥 SNIPED {mint_address[:8]} | Auto-sell in {sell_delay}s",
#                 "timestamp": datetime.utcnow().isoformat()
#             }), wallet_address)

#         except Exception as e:
#             logger.error(f"❌ Buy failed for {wallet_address}: {e}")
#             await websocket_manager.send_personal_message(json.dumps({
#                 "type": "log",
#                 "log_type": "error",
#                 "message": f"Snipe failed: {str(e)[:60]}",
#             }), wallet_address)


# async def execute_hyper_buy(user: User, token: TokenMetadata, db: AsyncSession):
#     """Ultra-fast buy without any filters or delays"""
#     mint = token.mint_address
#     lock_key = f"hyper_buy_lock:{user.wallet_address}:{mint}"
    
#     if await redis_client.get(lock_key):
#         return
    
#     await redis_client.setex(lock_key, 10, "1")  # 10s lock

#     try:
#         amount_lamports = int(user.buy_amount_sol * 1_000_000_000)
        
#         # Use maximum slippage for instant execution
#         slippage_bps = 5000  # 50% slippage for guaranteed execution
        
#         swap_data = await execute_jupiter_swap(
#             user=user,
#             input_mint=settings.SOL_MINT,
#             output_mint=mint,
#             amount_lamports=amount_lamports,
#             slippage_bps=slippage_bps,
#             label="HYPER_BUY",
#             priority_fee=500_000  # High priority fee for speed
#         )

#         # Calculate token amount (estimate since we don't have decimals yet)
#         token_amount = swap_data["out_amount"] / 1_000_000_000  # Rough estimate

#         trade = Trade(
#             user_wallet_address=user.wallet_address,
#             mint_address=mint,
#             token_symbol=token.token_symbol or mint[:8],
#             trade_type="buy",
#             amount_sol_in=user.buy_amount_sol,
#             amount_tokens=token_amount,
#             price_usd_at_trade=0.0,  # We don't know the price yet
#             buy_timestamp=datetime.utcnow(),
#             take_profit_target=10.0,  # Minimal profit target for quick flip
#             stop_loss_target=50.0,    # Wide stop loss to avoid premature selling
#         )
#         db.add(trade)
#         await db.commit()

#         logger.info(f"✅ HYPER BUY COMPLETE → {user.wallet_address[:6]} bought {mint[:8]}")

#     except Exception as e:
#         logger.error(f"❌ Hyper buy execution failed: {e}")
#         raise
#     finally:
#         await redis_client.delete(lock_key)


# async def auto_sell_after_delay(user: User, mint_address: str, sell_delay: int):
#     """Auto-sell after specified delay"""
#     await asyncio.sleep(sell_delay)

#     async with AsyncSessionLocal() as db:
#         # Find the open trade
#         trade = (await db.execute(select(Trade).where(
#             Trade.user_wallet_address == user.wallet_address,
#             Trade.mint_address == mint_address,
#             Trade.sell_timestamp.is_(None)
#         ))).scalar_one_or_none()

#         if not trade:
#             logger.info(f"❌ No open position found for {user.wallet_address[:6]} - {mint_address[:8]}")
#             return

#         logger.info(f"💰 AUTO-SELL → {user.wallet_address[:6]} selling {mint_address[:8]} after {sell_delay}s")

#         try:
#             # Get current token balance
#             async with AsyncClient(settings.SOLANA_RPC_URL) as client:
#                 # Get token account
#                 token_account = await client.get_token_accounts_by_owner(
#                     Pubkey.from_string(user.wallet_address),
#                     {"mint": Pubkey.from_string(mint_address)}
#                 )
                
#                 if not token_account.value:
#                     logger.error(f"❌ No token account found for {mint_address[:8]}")
#                     return
                    
#                 token_balance = token_account.value[0].account.data.parsed['info']['tokenAmount']['amount']
                
#                 if token_balance == 0:
#                     logger.error(f"❌ Zero token balance for {mint_address[:8]}")
#                     return

#             # Execute sell with high slippage for guaranteed execution
#             swap_data = await execute_jupiter_swap(
#                 user=user,
#                 input_mint=mint_address,
#                 output_mint=settings.SOL_MINT,
#                 amount_lamports=token_balance,
#                 slippage_bps=5000,  # 50% slippage
#                 label="HYPER_SELL",
#                 priority_fee=500_000
#             )

#             # Update trade record
#             trade.sell_timestamp = datetime.utcnow()
#             trade.sell_tx_hash = "hyper_snipe_sell"
#             trade.sell_reason = f"hyper_snipe_{sell_delay}s_exit"
#             await db.commit()

#             logger.info(f"✅ AUTO-SELL COMPLETE → {user.wallet_address[:6]} sold {mint_address[:8]}")

#             await websocket_manager.send_personal_message(json.dumps({
#                 "type": "log",
#                 "log_type": "success",
#                 "message": f"💰 Auto-sold {mint_address[:8]} after {sell_delay}s",
#             }), user.wallet_address)

#         except Exception as e:
#             logger.error(f"❌ Auto-sell failed for {user.wallet_address[:6]}: {e}")
#             await websocket_manager.send_personal_message(json.dumps({
#                 "type": "log",
#                 "log_type": "error",
#                 "message": f"Auto-sell failed: {str(e)[:60]}",
#             }), user.wallet_address)


# # ===================================================================
# # PERSISTENT BOT MANAGEMENT
# # ===================================================================

# async def save_bot_state(wallet_address: str, is_running: bool, settings: dict = None):
#     """Save bot state to Redis for persistence"""
#     state = {
#         "is_running": is_running,
#         "last_heartbeat": datetime.utcnow().isoformat(),
#         "settings": settings or {}
#     }
#     await redis_client.setex(f"bot_state:{wallet_address}", 86400, json.dumps(state))

# async def load_bot_state(wallet_address: str) -> Optional[dict]:
#     """Load bot state from Redis"""
#     state_data = await redis_client.get(f"bot_state:{wallet_address}")
#     if state_data:
#         return json.loads(state_data)
#     return None

# async def start_persistent_bot_for_user(wallet_address: str):
#     """Start a persistent bot that survives browser closures"""
#     if wallet_address in active_bot_tasks and not active_bot_tasks[wallet_address].done():
#         logger.info(f"Bot already running for {wallet_address}")
#         return
    
#     async def persistent_bot_loop():
#         logger.info(f"Starting persistent bot for {wallet_address}")
        
#         while True:
#             try:
#                 # Check if bot should still be running
#                 state = await load_bot_state(wallet_address)
#                 if not state or not state.get("is_running", False):
#                     logger.info(f"Bot stopped via state for {wallet_address}")
#                     break
                
#                 # Get fresh user data each iteration
#                 async with AsyncSessionLocal() as db:
#                     user_result = await db.execute(
#                         select(User).where(User.wallet_address == wallet_address)
#                     )
#                     user = user_result.scalar_one_or_none()
                    
#                     if not user:
#                         logger.error(f"User {wallet_address} not found - stopping bot")
#                         await save_bot_state(wallet_address, False)
#                         break
                    
#                     # Check balance
#                     try:
#                         async with AsyncClient(settings.SOLANA_RPC_URL) as client:
#                             balance_response = await client.get_balance(Pubkey.from_string(wallet_address))
#                             sol_balance = balance_response.value / 1_000_000_000
                            
#                             if sol_balance < 0.1:
#                                 logger.info(f"Insufficient balance for {wallet_address}: {sol_balance} SOL")
#                                 await websocket_manager.send_personal_message(json.dumps({
#                                     "type": "log",
#                                     "log_type": "warning", 
#                                     "message": f"Low balance: {sol_balance:.4f} SOL. Bot paused.",
#                                     "timestamp": datetime.utcnow().isoformat()
#                                 }), wallet_address)
#                                 await asyncio.sleep(60)
#                                 continue
#                     except Exception as e:
#                         logger.error(f"Balance check failed for {wallet_address}: {e}")
#                         await asyncio.sleep(30)
#                         continue
                    
#                     # Process new tokens for this user (regular mode)
#                     await process_user_specific_tokens(user, db)
                    
#                 # Heartbeat
#                 await save_bot_state(wallet_address, True, {
#                     "last_cycle": datetime.utcnow().isoformat(),
#                     "balance": sol_balance
#                 })
                
#                 check_interval = user.bot_check_interval_seconds if user and user.bot_check_interval_seconds else 10
#                 await asyncio.sleep(check_interval)
                
#             except asyncio.CancelledError:
#                 logger.info(f"Persistent bot cancelled for {wallet_address}")
#                 break
#             except Exception as e:
#                 logger.error(f"Error in persistent bot for {wallet_address}: {e}")
#                 await asyncio.sleep(30)
        
#         # Cleanup
#         if wallet_address in active_bot_tasks:
#             del active_bot_tasks[wallet_address]
#         await save_bot_state(wallet_address, False)
#         logger.info(f"Persistent bot stopped for {wallet_address}")
    
#     task = asyncio.create_task(persistent_bot_loop())
#     active_bot_tasks[wallet_address] = task
#     await save_bot_state(wallet_address, True)

# async def process_user_specific_tokens(user: User, db: AsyncSession):
#     """Process tokens specifically for a user based on their filters (regular mode)"""
#     recent_time = datetime.utcnow() - timedelta(minutes=5)
    
#     result = await db.execute(
#         select(TokenMetadata)
#         .where(
#             TokenMetadata.last_checked_at >= recent_time,
#             TokenMetadata.trading_recommendation.in_(["MOONBAG_BUY", "STRONG_BUY", "BUY"]),
#             TokenMetadata.profitability_confidence >= 70
#         )
#         .order_by(TokenMetadata.profitability_score.desc())
#         .limit(10)
#     )
    
#     tokens = result.scalars().all()
    
#     for token in tokens:
#         existing_trade = await db.execute(
#             select(Trade).where(
#                 Trade.user_wallet_address == user.wallet_address,
#                 Trade.mint_address == token.mint_address,
#                 Trade.sell_timestamp.is_(None)
#             )
#         )
#         if existing_trade.scalar_one_or_none():
#             continue
        
#         # Apply user-specific filters for regular trading
#         if await apply_user_filters(user, token, db, websocket_manager):
#             await execute_user_buy(user, token, db, websocket_manager)
#             await asyncio.sleep(1)

# async def restore_persistent_bots():
#     """Restore all persistent bots on startup"""
#     try:
#         keys = await redis_client.keys("bot_state:*")
#         for key in keys:
#             state_data = await redis_client.get(key)
#             if state_data:
#                 state = json.loads(state_data)
#                 if state.get("is_running", False):
#                     wallet_address = key.decode().replace("bot_state:", "")
#                     await asyncio.sleep(1)
#                     asyncio.create_task(start_persistent_bot_for_user(wallet_address))
#                     logger.info(f"Restored persistent bot for {wallet_address}")
#     except Exception as e:
#         logger.error(f"Error restoring persistent bots: {e}")

# # ===================================================================
# # LIFESPAN MANAGEMENT
# # ===================================================================

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     try:
#         async with database.async_engine.begin() as conn:
#             await conn.run_sync(models.Base.metadata.create_all)
        
#         # Start core services
#         asyncio.create_task(safe_raydium_grpc_loop())
#         asyncio.create_task(safe_metadata_enrichment_loop())
#         asyncio.create_task(restore_persistent_bots())
        
#         logger.info("🚀 HYPER SNIPER 2025 STARTED - INSTANT 3s SNIPES ACTIVATED!")
#         yield
#     except Exception as e:
#         logger.error(f"❌ Startup failed: {e}")
#         raise
#     finally:
#         for task in active_bot_tasks.values():
#             task.cancel()
#         await asyncio.gather(*active_bot_tasks.values(), return_exceptions=True)
#         await redis_client.close()
#         await database.async_engine.dispose()

# app.router.lifespan_context = lifespan

# # ===================================================================
# # gRPC RAYDIUM POOL DETECTION (INSTANT SNIPE TRIGGER)
# # ===================================================================

# def create_grpc_channel(endpoint: str, token: str) -> grpc.aio.Channel:
#     endpoint = endpoint.replace('http://', '').replace('https://', '')
#     auth_creds = grpc.metadata_call_credentials(
#         lambda context, callback: callback((("x-token", token),), None)
#     )
#     ssl_creds = grpc.ssl_channel_credentials()
#     options = (
#         ('grpc.ssl_target_name_override', endpoint.split(':')[0]),
#         ('grpc.default_authority', endpoint.split(':')[0]),
#         ('grpc.keepalive_time_ms', 10000),
#         ('grpc.keepalive_timeout_ms', 5000),
#         ('grpc.keepalive_permit_without_calls', 1),
#     )
#     combined_creds = grpc.composite_channel_credentials(ssl_creds, auth_creds)
#     return grpc.aio.secure_channel(endpoint, combined_creds, options=options)

# async def safe_raydium_grpc_loop():
#     while True:
#         try:
#             await raydium_grpc_subscription_loop()
#         except Exception as e:
#             logger.error(f"Raydium loop crashed: {e}")
#             await asyncio.sleep(10)

# async def raydium_grpc_subscription_loop():
#     program_id = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
#     grpc_url = os.getenv("GRPC_URL", "grpc.ams.shyft.to:443")
#     grpc_token = os.getenv("GRPC_TOKEN", "30c7ef87-5bf0-4d70-be9f-3ea432922437")

#     while True:
#         channel = None
#         try:
#             channel = create_grpc_channel(grpc_url, grpc_token)
#             stub = GeyserStub(channel)

#             subscribe_request = SubscribeRequest(
#                 transactions={
#                     "raydium_pools": {
#                         "vote": False,
#                         "failed": False,
#                         "account_include": [program_id],
#                     }
#                 },
#                 commitment=CommitmentLevel.CONFIRMED,
#             )

#             async for response in stub.Subscribe(iter([subscribe_request])):
#                 if not response.HasField('transaction'):
#                     continue

#                 tx_info = response.transaction
                
#                 signature = None
#                 if (hasattr(tx_info, 'transaction') and tx_info.transaction and
#                     hasattr(tx_info.transaction, 'signature') and tx_info.transaction.signature):
#                     signature_bytes = tx_info.transaction.signature
#                     signature = base58.b58encode(signature_bytes).decode()
#                 else:
#                     continue

#                 slot = getattr(tx_info, 'slot', 0)
#                 accounts = []
                
#                 try:
#                     if (hasattr(tx_info, 'transaction') and tx_info.transaction and
#                         hasattr(tx_info.transaction, 'transaction') and tx_info.transaction.transaction and
#                         hasattr(tx_info.transaction.transaction, 'message') and tx_info.transaction.transaction.message and
#                         hasattr(tx_info.transaction.transaction.message, 'account_keys')):
                        
#                         account_keys = tx_info.transaction.transaction.message.account_keys
#                         accounts = [base58.b58encode(key).decode() for key in account_keys]
                        
#                         if program_id in accounts:
#                             pool_infos = await find_raydium_pool_creations(tx_info, accounts, signature, slot)
                            
#                             if pool_infos:
#                                 logger.info(f"🎯 NEW POOL DETECTED! → {len(pool_infos)} pool(s)")
                                
#                                 # INSTANT SNIPE: Trigger hyper snipe immediately for each pool
#                                 for pool in pool_infos:
#                                     pool_data = pool["poolInfos"][0]
#                                     mint_address = pool_data["baseMint"]
                                    
#                                     # FIRE HYPER SNIPE IMMEDIATELY - NO DELAY!
#                                     asyncio.create_task(
#                                         instant_snipe_on_pool_creation(mint_address, pool_data)
#                                     )
                                    
#                                     # Also save to database for regular processing
#                                     asyncio.create_task(
#                                         save_pool_to_database(pool)
#                                     )
                            
#                 except Exception as e:
#                     continue

#         except grpc.aio.AioRpcError as e:
#             logger.error(f"gRPC error: {e.code()} - {e.details()}")
#             await asyncio.sleep(5)
#         except Exception as e:
#             logger.error(f"Unexpected error in Raydium gRPC: {e}")
#             await asyncio.sleep(5)
#         finally:
#             if channel is not None:
#                 await channel.close()
#             await asyncio.sleep(5)

# async def save_pool_to_database(pool: dict):
#     """Save pool to database for regular processing (non-instant mode)"""
#     async with AsyncSessionLocal() as db_session:
#         try:
#             pool_data = pool["poolInfos"][0]
#             pool_id = pool_data["id"]
#             mint = pool_data["baseMint"]

#             # Prevent duplicates
#             exists_pool = await db_session.get(NewTokens, pool_id)
#             if exists_pool:
#                 return

#             exists_mint = await db_session.execute(
#                 select(NewTokens).where(NewTokens.mint_address == mint)
#             )
#             if exists_mint.scalar_one_or_none():
#                 return

#             new_token = NewTokens(
#                 pool_id=pool_id,
#                 mint_address=mint,
#                 timestamp=datetime.utcnow(),
#                 signature=pool["txid"],
#                 tx_type="raydium_pool_create",
#                 metadata_status="pending",
#                 next_reprocess_time=datetime.utcnow(),
#                 dexscreener_processed=False,
#             )
#             db_session.add(new_token)
#             await db_session.commit()
            
#             logger.info(f"💾 Saved {mint[:8]} to database for regular processing")

#         except Exception as e:
#             logger.error(f"Error saving pool to database: {e}")

# async def find_raydium_pool_creations(tx_info, accounts, signature, slot):
#     """Extract Raydium pool creation information"""
#     program_id = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
#     pool_infos = []
    
#     try:
#         if program_id not in accounts:
#             return pool_infos

#         instructions = []
        
#         # Main instructions
#         if (hasattr(tx_info, 'transaction') and tx_info.transaction and
#             hasattr(tx_info.transaction, 'transaction') and tx_info.transaction.transaction and
#             hasattr(tx_info.transaction.transaction, 'message') and tx_info.transaction.transaction.message and
#             hasattr(tx_info.transaction.transaction.message, 'instructions')):
            
#             instructions.extend(tx_info.transaction.transaction.message.instructions)

#         # Inner instructions
#         if (hasattr(tx_info, 'transaction') and tx_info.transaction and
#             hasattr(tx_info.transaction, 'meta') and tx_info.transaction.meta and
#             hasattr(tx_info.transaction.meta, 'inner_instructions')):
            
#             for inner_instr in tx_info.transaction.meta.inner_instructions:
#                 if hasattr(inner_instr, 'instructions'):
#                     instructions.extend(inner_instr.instructions)

#         for instruction in instructions:
#             try:
#                 if instruction.program_id_index >= len(accounts):
#                     continue
                    
#                 instruction_program = accounts[instruction.program_id_index]
                
#                 if instruction_program != program_id:
#                     continue
                
#                 if (hasattr(instruction, 'data') and instruction.data and len(instruction.data) > 0):
#                     opcode = instruction.data[0]
                    
#                     if opcode == 1:  # Pool creation
#                         if len(instruction.accounts) < 17:
#                             continue
                            
#                         pool_id = accounts[instruction.accounts[4]]
                        
#                         pool_info = {
#                             "updateTime": datetime.utcnow().timestamp(),
#                             "slot": slot,
#                             "txid": signature,
#                             "poolInfos": [{
#                                 "id": pool_id,
#                                 "baseMint": accounts[instruction.accounts[8]],
#                                 "quoteMint": accounts[instruction.accounts[9]],
#                                 "lpMint": accounts[instruction.accounts[7]],
#                                 "version": 4,
#                                 "programId": program_id,
#                                 "authority": accounts[instruction.accounts[5]],
#                                 "openOrders": accounts[instruction.accounts[6]],
#                                 "targetOrders": accounts[instruction.accounts[12]],
#                                 "baseVault": accounts[instruction.accounts[10]],
#                                 "quoteVault": accounts[instruction.accounts[11]],
#                                 "marketId": accounts[instruction.accounts[16]],
#                             }]
#                         }
#                         pool_infos.append(pool_info)
                    
#             except Exception:
#                 continue
                
#     except Exception as e:
#         logger.error(f"Error finding Raydium pools: {e}")
        
#     return pool_infos

# # ===================================================================
# # REGULAR PROCESSING (NON-INSTANT MODE)
# # ===================================================================

# async def safe_metadata_enrichment_loop():
#     while True:
#         try:
#             await metadata_enrichment_loop()
#         except Exception as e:
#             logger.error(f"Metadata loop crashed: {e}")
#             await asyncio.sleep(30)
            
# async def metadata_enrichment_loop():
#     while True:
#         async with AsyncSessionLocal() as db:
#             stmt = select(NewTokens).where(
#                 NewTokens.metadata_status == "pending",
#                 or_(
#                     NewTokens.next_reprocess_time.is_(None),
#                     NewTokens.next_reprocess_time <= datetime.utcnow()
#                 )
#             ).order_by(NewTokens.timestamp).limit(15)

#             result = await db.execute(stmt)
#             pending = result.scalars().all()

#             tasks = [safe_enrich_token(t.mint_address, db) for t in pending]
#             await asyncio.gather(*tasks, return_exceptions=True)

#         await asyncio.sleep(6)
        
# async def safe_enrich_token(mint_address: str, db: AsyncSession):
#     try:
#         await process_token_logic(mint_address, db)

#         new_token_result = await db.execute(
#             select(NewTokens).where(NewTokens.mint_address == mint_address)
#         )
#         token = new_token_result.scalar_one_or_none()
        
#         if token:
#             token.metadata_status = "processed"
#             token.last_metadata_update = datetime.utcnow()
#             await db.commit()
            
#     except Exception as e:
#         logger.error(f"Failed to enrich {mint_address}: {e}")

# @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
# async def process_token_logic(mint_address: str, db: AsyncSession):
#     try:
#         # Regular token processing (not for instant snipe)
#         result = await db.execute(select(TokenMetadata).where(TokenMetadata.mint_address == mint_address))
#         token = result.scalars().first()
#         if not token:
#             token = TokenMetadata(mint_address=mint_address)
#             db.add(token)
#             await db.flush()

#         # DexScreener data
#         dex_data = await fetch_dexscreener_with_retry(mint_address)
#         if not dex_data:
#             token.trading_recommendation = "NO_DEXSCREENER"
#             token.last_checked_at = datetime.utcnow()
#             await db.merge(token)
#             await db.commit()
#             return

#         # Populate data...
#         if dex_data:
#             token.dexscreener_url = dex_data.get("dexscreener_url")
#             token.pair_address = dex_data.get("pair_address")
#             token.price_usd = safe_float(dex_data.get("price_usd"))
#             token.market_cap = safe_float(dex_data.get("market_cap"))
#             token.pair_created_at = dex_data.get("pair_created_at")
#             token.twitter = dex_data.get("twitter")
#             token.telegram = dex_data.get("telegram")
#             token.token_name = dex_data.get("token_name")
#             token.token_symbol = dex_data.get("token_symbol")
#             token.volume_h24 = safe_float(dex_data.get("volume_h24"))
#             token.socials_present = bool(dex_data.get("twitter") or dex_data.get("telegram"))
#             token.liquidity_usd = safe_float(dex_data.get("liquidity_usd"))
#             token.fdv = safe_float(dex_data.get("fdv"))

#         # Webacy data
#         try:
#             webacy_data = await check_webacy_risk(mint_address)
#             if webacy_data and isinstance(webacy_data, dict):
#                 token.webacy_risk_score = safe_float(webacy_data.get("risk_score"))
#                 token.webacy_risk_level = webacy_data.get("risk_level")
#                 token.webacy_moon_potential = webacy_data.get("moon_potential")
#         except:
#             pass

#         # Profitability engine
#         try:
#             token_dict = {}
#             for key, value in token.__dict__.items():
#                 if not key.startswith('_'):
#                     if isinstance(value, datetime):
#                         token_dict[key] = value.isoformat()
#                     else:
#                         token_dict[key] = value
            
#             analysis = await profitability_engine.analyze_token(
#                 mint=mint_address,
#                 token_data=token_dict,
#                 webacy_data=webacy_data or {}
#             )
            
#             token.profitability_score = analysis.final_score
#             token.profitability_confidence = analysis.confidence
#             token.trading_recommendation = analysis.recommendation

#         except Exception as e:
#             logger.error(f"Profitability engine error: {e}")
#             token.trading_recommendation = "ERROR"

#         token.last_checked_at = datetime.utcnow()
#         db.add(token)
#         await db.commit()

#     except Exception as e:
#         logger.error(f"CRITICAL FAILURE in process_token_logic: {e}")
#         await db.rollback()

# async def fetch_dexscreener_with_retry(mint: str, max_attempts: int = 9) -> dict:
#     for attempt in range(max_attempts):
#         data = await get_dexscreener_data(mint)
#         price_usd = 0.0
#         if data and data.get("price_usd"):
#             try:
#                 price_usd = float(data["price_usd"])
#             except (ValueError, TypeError):
#                 price_usd = 0.0

#         if price_usd > 0:
#             return data

#         delay = min(8 + (attempt ** 2) * 7, 160)
#         await asyncio.sleep(delay)

#     return {}

# def safe_float(value, default=0.0) -> float:
#     try:
#         return float(value) if value not in (None, "", "null") else default
#     except:
#         return default

# # ===================================================================
# # USER FILTERS (FOR REGULAR TRADING ONLY)
# # ===================================================================

# async def apply_user_filters(user: User, token_meta: TokenMetadata, db: AsyncSession, websocket_manager: ConnectionManager) -> bool:
#     async def log_failure(filter_name: str, details: str = ""):
#         symbol = token_meta.token_symbol or token_meta.mint_address[:8]
#         msg = f"Token {symbol} failed {filter_name} filter."
#         if details:
#             msg += f" {details}"
#         logger.info(msg)
#         await websocket_manager.send_personal_message(
#             json.dumps({
#                 "type": "log",
#                 "log_type": "warning",
#                 "message": msg,
#                 "timestamp": datetime.utcnow().isoformat()
#             }),
#             user.wallet_address
#         )

#     # Basic filters for regular trading
#     min_liq_sol = user.filter_check_pool_size_min_sol or 0.05
#     current_liq = token_meta.liquidity_pool_size_sol
    
#     if current_liq is None or current_liq < min_liq_sol:
#         await log_failure("Insufficient Liquidity", f"{current_liq or 0:.4f} SOL < {min_liq_sol} SOL required")
#         return False

#     if token_meta.pair_created_at:
#         age_seconds = datetime.utcnow().timestamp() - token_meta.pair_created_at
#         if age_seconds < 15:
#             await log_failure("Token Too New", f"Only {int(age_seconds)}s old")
#             return False

#     if token_meta.market_cap is not None and token_meta.market_cap < 30_000:
#         await log_failure("Market Cap Too Low", f"${token_meta.market_cap:,.0f}")
#         return False

#     if token_meta.webacy_risk_score is not None and token_meta.webacy_risk_score > 50:
#         await log_failure("Webacy Risk Too High", f"Score: {token_meta.webacy_risk_score:.1f}")
#         return False

#     return True

# # ===================================================================
# # WEB SOCKET & API ENDPOINTS (REMAIN THE SAME)
# # ===================================================================

# @app.websocket("/ws/logs/{wallet_address}")
# async def websocket_endpoint(websocket: WebSocket, wallet_address: str):
#     await websocket_manager.connect(websocket, wallet_address)
    
#     try:
#         # Send current bot status
#         state = await load_bot_state(wallet_address)
#         is_running = state.get("is_running", False) if state else False
        
#         await websocket.send_json({
#             "type": "bot_status",
#             "is_running": is_running,
#             "message": "Bot is running persistently" if is_running else "Bot is stopped"
#         })
        
#         # Send recent trades
#         async with AsyncSessionLocal() as db:
#             result = await db.execute(
#                 select(Trade)
#                 .filter_by(user_wallet_address=wallet_address)
#                 .order_by(Trade.id.desc())
#                 .limit(50)
#             )
#             trades = result.scalars().all()
#             for trade in trades:
#                 await websocket.send_json({
#                     "type": "trade_update",
#                     "trade": {
#                         "id": trade.id,
#                         "trade_type": trade.trade_type,
#                         "amount_sol": trade.amount_sol_in or trade.amount_sol_out or 0,
#                         "token_symbol": trade.token_symbol or "Unknown",
#                         "timestamp": trade.created_at.isoformat() if trade.created_at else None,
#                     }
#                 })
        
#         # Handle messages with proper error handling
#         while True:
#             try:
#                 data = await websocket.receive_text()
#                 if data:
#                     try:
#                         message = json.loads(data)
#                         await handle_websocket_message(message, wallet_address, websocket)
#                     except json.JSONDecodeError as e:
#                         logger.error(f"Invalid JSON from {wallet_address}: {data}")
#                         await websocket.send_json({
#                             "type": "error",
#                             "message": "Invalid JSON format"
#                         })
#                     except Exception as e:
#                         logger.error(f"Error processing message from {wallet_address}: {e}")
#                         await websocket.send_json({
#                             "type": "error", 
#                             "message": f"Error processing message: {str(e)}"
#                         })
#             except WebSocketDisconnect:
#                 break
#             except Exception as e:
#                 logger.error(f"WebSocket receive error for {wallet_address}: {e}")
#                 break
                    
#     except WebSocketDisconnect:
#         logger.info(f"WebSocket disconnected for {wallet_address}")
#     except Exception as e:
#         logger.error(f"WebSocket error for {wallet_address}: {str(e)}")
#     finally:
#         websocket_manager.disconnect(wallet_address)
#         logger.info(f"WebSocket connection closed for {wallet_address}")
        
# async def handle_websocket_message(message: dict, wallet_address: str, websocket: WebSocket):
#     """Handle different types of WebSocket messages"""
#     msg_type = message.get("type")
    
#     if msg_type == "start_bot":
#         await start_persistent_bot_for_user(wallet_address)
#         await websocket.send_json({
#             "type": "bot_status", 
#             "is_running": True,
#             "message": "Bot started successfully"
#         })
        
#     elif msg_type == "stop_bot":
#         await save_bot_state(wallet_address, False)
#         await websocket.send_json({
#             "type": "bot_status",
#             "is_running": False, 
#             "message": "Bot stopped successfully"
#         })
        
#     elif msg_type == "health_response":
#         logger.debug(f"Health response from {wallet_address}")
        
#     elif msg_type == "settings_update":
#         async with AsyncSessionLocal() as db:
#             await update_bot_settings(message.get("settings", {}), wallet_address, db)
            
#     elif msg_type == "ping":
#         # Handle ping messages
#         await websocket.send_json({
#             "type": "pong",
#             "timestamp": datetime.utcnow().isoformat()
#         })

# async def update_bot_settings(settings: dict, wallet_address: str, db: AsyncSession):
#     try:
#         stmt = select(User).filter(User.wallet_address == wallet_address)
#         result = await db.execute(stmt)
#         user = result.scalar_one_or_none()
#         if not user:
#             raise ValueError("User not found")
        
#         # Update only the settings that are provided
#         for key, value in settings.items():
#             if hasattr(user, key):
#                 setattr(user, key, value)
        
#         await db.commit()
        
#         await websocket_manager.send_personal_message(
#             json.dumps({
#                 "type": "log", 
#                 "message": "Bot settings updated successfully", 
#                 "status": "info"
#             }),
#             wallet_address
#         )
        
#     except Exception as e:
#         logger.error(f"Error updating settings for {wallet_address}: {e}")
#         await websocket_manager.send_personal_message(
#             json.dumps({
#                 "type": "log", 
#                 "message": f"Settings update error: {str(e)}", 
#                 "status": "error"
#             }),
#             wallet_address
#         )
#         await db.rollback()
        
         
# # ===================================================================
# # 4. ALL MAIN ENDPOINTS STARTS HERE
# # ===================================================================
# @app.get("/ping")
# async def ping():
#     logger.info("Ping received.")
#     return {"message": "pong", "status": "ok"}

# @app.get("/health")
# async def health_check():
#     try:
#         async with AsyncClient(settings.SOLANA_RPC_URL) as client:
#             await client.is_connected()
#         try:
#             channel = create_grpc_channel(
#                 os.getenv("GRPC_URL", "grpc.mainnet.solana.yellowstone.dev:10000"),
#                 os.getenv("GRPC_TOKEN", "your-grpc-token")
#             )
#             stub = GeyserStub(channel)
#             await stub.GetVersion(GetVersionRequest())
#             grpc_status = "ok"
#             await channel.close()
#         except Exception as e:
#             grpc_status = f"error: {e}"
#         return {
#             "status": "healthy",
#             "database": "ok",
#             "solana_rpc": "ok",
#             "grpc_raydium": grpc_status,
#             "message": "All essential services are operational."
#         }
#     except Exception as e:
#         logger.error(f"Health check failed: {e}")
#         return {"status": "unhealthy", "message": str(e)}

# @app.get("/debug/routes")
# async def debug():
#     return [{"path": r.path, "name": r.name} for r in app.routes]

# async def handle_websocket_message(message: dict, wallet_address: str, websocket: WebSocket):
#     """Handle different types of WebSocket messages"""
#     msg_type = message.get("type")
    
#     if msg_type == "start_bot":
#         await start_persistent_bot_for_user(wallet_address)
#         await websocket.send_json({
#             "type": "bot_status", 
#             "is_running": True,
#             "message": "Bot started successfully"
#         })
        
#     elif msg_type == "stop_bot":
#         await save_bot_state(wallet_address, False)
#         await websocket.send_json({
#             "type": "bot_status",
#             "is_running": False, 
#             "message": "Bot stopped successfully"
#         })
        
#     elif msg_type == "health_response":
#         logger.debug(f"Health response from {wallet_address}")
        
#     elif msg_type == "settings_update":
#         async with AsyncSessionLocal() as db:
#             await update_bot_settings(message.get("settings", {}), wallet_address, db)  # FIXED THIS LINE
            
#     elif msg_type == "ping":
#         # Handle ping messages
#         await websocket.send_json({
#             "type": "pong",
#             "timestamp": datetime.utcnow().isoformat()
#         })
         
# @app.post("/user/update-rpc")
# async def update_user_rpc(
#     rpc_data: dict,
#     current_user: User = Depends(get_current_user_by_wallet),
#     db: AsyncSession = Depends(get_db)
# ):
#     if not current_user.is_premium:
#         raise HTTPException(status_code=403, detail="Custom RPC is available only for premium users.")
#     https_url = rpc_data.get("https")
#     wss_url = rpc_data.get("wss")
#     if https_url and not https_url.startswith("https://"):
#         raise HTTPException(status_code=400, detail="Invalid HTTPS RPC URL")
#     if wss_url and not wss_url.startswith("wss://"):
#         raise HTTPException(status_code=400, detail="Invalid WSS RPC URL")
#     current_user.custom_rpc_https = https_url
#     current_user.custom_rpc_wss = wss_url
#     await db.merge(current_user)
#     await db.commit()
#     return {"status": "Custom RPC settings updated."}

# @app.get("/wallet/balance/{wallet_address}")
# async def get_wallet_balance(wallet_address: str):
#     try:
#         async with AsyncClient(settings.SOLANA_RPC_URL) as client:
#             pubkey = Pubkey.from_string(wallet_address)
#             balance_response = await client.get_balance(pubkey)
#             lamports = balance_response.value
#             sol_balance = lamports / 1_000_000_000
#             return {"wallet_address": wallet_address, "sol_balance": sol_balance}
#     except Exception as e:
#         logger.error(f"Error fetching balance for {wallet_address}: {e}")
#         raise HTTPException(status_code=500, detail=f"Error fetching balance: {str(e)}")

# @app.post("/trade/log-trade")
# async def log_trade(
#     trade_data: LogTradeRequest,
#     current_user: User = Depends(get_current_user_by_wallet),
#     db: AsyncSession = Depends(get_db)
# ):
#     fee_percentage = 0.01
#     fee_sol = trade_data.amount_sol * fee_percentage if trade_data.amount_sol else 0
#     amount_after_fee = trade_data.amount_sol - fee_sol if trade_data.amount_sol else 0
#     trade = Trade(
#         user_wallet_address=current_user.wallet_address,
#         mint_address=trade_data.mint_address,
#         token_symbol=trade_data.token_symbol,
#         trade_type=trade_data.trade_type,
#         amount_sol=amount_after_fee,
#         amount_tokens=trade_data.amount_tokens,
#         price_sol_per_token=trade_data.price_sol_per_token,
#         price_usd_at_trade=trade_data.price_usd_at_trade,
#         buy_tx_hash=trade_data.tx_hash if trade_data.trade_type == "buy" else None,
#         sell_tx_hash=trade_data.tx_hash if trade_data.trade_type == "sell" else None,
#         profit_usd=trade_data.profit_usd,
#         profit_sol=trade_data.profit_sol,
#         log_message=trade_data.log_message,
#         buy_price=trade_data.buy_price,
#         entry_price=trade_data.entry_price,
#         stop_loss=trade_data.stop_loss,
#         take_profit=trade_data.take_profit,
#         token_amounts_purchased=trade_data.token_amounts_purchased,
#         token_decimals=trade_data.token_decimals,
#         sell_reason=trade_data.sell_reason,
#         swap_provider=trade_data.swap_provider,
#         buy_timestamp=datetime.utcnow() if trade_data.trade_type == "buy" else None,
#         sell_timestamp=datetime.utcnow() if trade_data.trade_type == "sell" else None,
#     )
#     db.add(trade)
#     await db.commit()
#     await websocket_manager.send_personal_message(
#         json.dumps({"type": "log", "message": f"Applied 1% fee ({fee_sol:.6f} SOL) on {trade_data.trade_type} trade.", "status": "info"}),
#         current_user.wallet_address
#     )
#     return {"status": "Trade logged successfully."}

# @app.get("/trade/history")
# async def get_trade_history(
#     current_user: User = Depends(get_current_user_by_wallet),
#     db: AsyncSession = Depends(get_db)
# ):
#     trades = await db.execute(
#         select(Trade)
#         .filter(Trade.user_wallet_address == current_user.wallet_address)
#         .order_by(Trade.buy_timestamp.desc())
#     )
#     trades = trades.scalars().all()

#     result = []
#     for trade in trades:
#         data = trade.__dict__.copy()
        
#         # If token still in hot table → use live data
#         meta = await db.get(TokenMetadata, trade.mint_address)
#         if not meta:
#             # Fallback to archive
#             arch = await db.execute(
#                 select(TokenMetadataArchive.data)
#                 .where(TokenMetadataArchive.mint_address == trade.mint_address)
#                 .order_by(TokenMetadataArchive.archived_at.desc())
#             )
#             arch_data = arch.scalar()
#             if arch_data:
#                 archived = json.loads(arch_data)
#                 data["token_symbol"] = archived.get("token_symbol", "Unknown")
#                 data["token_name"] = archived.get("token_name", "Unknown Token")
#                 data["token_logo_uri"] = archived.get("token_logo_uri")
#             else:
#                 data["token_symbol"] = trade.token_symbol or trade.mint_address[:8]
#         else:
#             data["token_symbol"] = meta.token_symbol or trade.token_symbol
#             data["token_name"] = meta.token_name
        
#         result.append(data)

#     return result

# @app.post("/subscribe/premium")
# async def subscribe_premium(
#     subscription_data: SubscriptionRequest,
#     current_user: User = Depends(get_current_user_by_wallet),
#     db: AsyncSession = Depends(get_db)
# ):
#     try:
#         import stripe
#         stripe.api_key = settings.STRIPE_SECRET_KEY
#         subscription = stripe.Subscription.create(
#             customer={"email": subscription_data.email},
#             items=[{"price": settings.STRIPE_PREMIUM_PRICE_ID}],
#             payment_behavior="default_incomplete",
#             expand=["latest_invoice.payment_intent"]
#         )
#         sub = Subscription(
#             user_wallet_address=current_user.wallet_address,
#             plan_name="Premium",
#             payment_provider_id=subscription.id,
#             start_date=datetime.utcnow(),
#             end_date=datetime.utcnow() + timedelta(days=30)
#         )
#         current_user.is_premium = True
#         current_user.premium_start_date = datetime.utcnow()
#         current_user.premium_end_date = datetime.utcnow() + timedelta(days=30)
#         db.add(sub)
#         await db.merge(current_user)
#         await db.commit()
#         return {"status": "Subscription activated", "payment_intent": subscription.latest_invoice.payment_intent}
#     except Exception as e:
#         logger.error(f"Subscription failed: {e}")
#         raise HTTPException(status_code=400, detail=f"Subscription failed: {str(e)}")

  
  
  
  
  
  