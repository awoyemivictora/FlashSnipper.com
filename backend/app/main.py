# app/main.py
import logging
import os
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import json
import asyncio
import traceback
from typing import Dict, Optional
from datetime import datetime, timedelta
import grpc
import base58
import base64
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solana.rpc.async_api import AsyncClient
from jupiter_python_sdk.jupiter import Jupiter
from app.dependencies import get_current_user_by_wallet
from app.models import Subscription, Trade, User, TokenMetadata, NewTokens
from app.database import AsyncSessionLocal, get_db
from app.schemas import LogTradeRequest, SubscriptionRequest
from app.utils.dexscreener_api import get_dexscreener_data
from app.utils.raydium_apis import get_raydium_pool_info
from app.utils.solscan_apis import get_solscan_token_meta, get_top_holders_info
from app.utils.webacy_api import check_webacy_risk
from app import models, database
from app.config import settings
from app.security import decrypt_private_key_backend
import redis.asyncio as redis

# Add generated stubs
import sys
sys.path.append('app/generated')
from app.generated.geyser_pb2 import SubscribeRequest, GetVersionRequest, CommitmentLevel
from app.generated.geyser_pb2_grpc import GeyserStub

# Disable SQLAlchemy logging
logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'loggers': {
        'sqlalchemy.engine': {'level': 'ERROR', 'handlers': [], 'propagate': False},
        'sqlalchemy.pool': {'level': 'ERROR', 'handlers': [], 'propagate': False},
        'sqlalchemy.dialects': {'level': 'ERROR', 'handlers': [], 'propagate': False},
    }
})

# Load environment variables
load_dotenv()

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False

# Redis client
redis_client = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379, db=0)

# FastAPI app
app = FastAPI(
    title="Solsniper API",
    description="A powerful Solana sniping bot with AI analysis and rug pull protection.",
    version="0.2.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # DEV ONLY
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers AFTER app creation to avoid circular imports
from app.routers import auth, token, trade, user, util

# Include routers
app.include_router(auth.router)
app.include_router(token.router)
app.include_router(trade.router)
app.include_router(user.router)
app.include_router(util.router)

# Add the missing dependency function here to avoid circular imports
from app.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException, status
from sqlalchemy import select


# Lifespan event handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with database.async_engine.begin() as conn:
            await conn.run_sync(models.Base.metadata.create_all)
        asyncio.create_task(safe_raydium_grpc_loop())
        asyncio.create_task(safe_metadata_enrichment_loop())
        logger.info("🚀 Production backend started successfully")
        yield
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise
    finally:
        await redis_client.close()
        await database.async_engine.dispose()

# Attach lifespan to app
app.router.lifespan_context = lifespan

# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

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
            except Exception as e:
                logger.error(f"Error sending message to {wallet_address}: {e}")
                self.disconnect(wallet_address)

websocket_manager = ConnectionManager()

# Active bot tasks
active_bot_tasks: Dict[str, asyncio.Task] = {}

@app.get("/debug/routes")
async def debug():
    return [{"path": r.path, "name": r.name} for r in app.routes]

# WebSocket endpoint
@app.websocket("/ws/logs/{wallet_address}")
async def websocket_endpoint(websocket: WebSocket, wallet_address: str):
    await websocket_manager.connect(websocket, wallet_address)
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Trade)
                .filter_by(user_wallet_address=wallet_address)   # ← FIXED
                .order_by(Trade.id.desc())                      # ← better than created_at which doesn't exist
                .limit(50)
            )
            trades = result.scalars().all()
            for trade in trades:
                await websocket.send_json({
                    "type": "trade_update",
                    "trade": {
                        "id": trade.id,
                        "trade_type": trade.trade_type,
                        "amount_sol": trade.amount_sol_in or trade.amount_sol_out or 0,
                        "token_symbol": trade.token_symbol or "Unknown",
                        "timestamp": trade.created_at.isoformat() if trade.created_at else None,
                    }
                })
        
        while True:
            data = await websocket.receive_text()
            if data:
                try:
                    message = json.loads(data)
                    if message.get("type") == "health_response":
                        logger.info(f"Received health response from {wallet_address}")
                except json.JSONDecodeError:
                    logger.error(f"Invalid WebSocket message from {wallet_address}")
    except WebSocketDisconnect:
        websocket_manager.disconnect(wallet_address)
    except Exception as e:
        logger.error(f"WebSocket error for {wallet_address}: {str(e)}")
        websocket_manager.disconnect(wallet_address)


# gRPC Channel
def create_grpc_channel(endpoint: str, token: str) -> grpc.aio.Channel:
    endpoint = endpoint.replace('http://', '').replace('https://', '')
    logger.info(f"Creating gRPC channel to {endpoint} with token: {token[:8]}...")
    auth_creds = grpc.metadata_call_credentials(
        lambda context, callback: callback((("x-token", token),), None)
    )
    ssl_creds = grpc.ssl_channel_credentials()
    options = (
        ('grpc.ssl_target_name_override', endpoint.split(':')[0]),
        ('grpc.default_authority', endpoint.split(':')[0]),
        ('grpc.keepalive_time_ms', 10000),
        ('grpc.keepalive_timeout_ms', 5000),
        ('grpc.keepalive_permit_without_calls', 1),
    )
    combined_creds = grpc.composite_channel_credentials(ssl_creds, auth_creds)
    channel = grpc.aio.secure_channel(endpoint, combined_creds, options=options)
    logger.info(f"gRPC channel created: {endpoint}")
    return channel

# Raydium gRPC loop and other functions remain unchanged
async def safe_raydium_grpc_loop():
    while True:
        try:
            await raydium_grpc_subscription_loop()
        except Exception as e:
            logger.error(f"Raydium loop crashed: {e}")
            await asyncio.sleep(30)

async def safe_metadata_enrichment_loop():
    while True:
        try:
            await metadata_enrichment_loop()
        except Exception as e:
            logger.error(f"Metadata loop crashed: {e}")
            await asyncio.sleep(30)
            

# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

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
            except Exception as e:
                logger.error(f"Error sending message to {wallet_address}: {e}")
                self.disconnect(wallet_address)

websocket_manager = ConnectionManager()

# Active bot tasks
active_bot_tasks: Dict[str, asyncio.Task] = {}

# # Update WebSocket endpoint
# @app.websocket("/ws/logs/{wallet_address}")
# async def websocket_endpoint(websocket: WebSocket, wallet_address: str):
#     await websocket_manager.connect(websocket, wallet_address)
#     try:
#         # Send initial trade history
#         async with AsyncSessionLocal() as db:
#             result = await db.execute(
#                 select(Trade)
#                 .filter_by(user_wallet_address=wallet_address)   # ← FIXED
#                 .order_by(Trade.id.desc())                      # ← better than created_at which doesn't exist
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
        
#         # Keep connection open for new trade updates
#         while True:
#             data = await websocket.receive_text()
#             # Handle client messages (e.g., health_response)
#             if data:
#                 try:
#                     message = json.loads(data)
#                     if message.get("type") == "health_response":
#                         logger.info(f"Received health response from {wallet_address}")
#                 except json.JSONDecodeError:
#                     logger.error(f"Invalid WebSocket message from {wallet_address}")
#     except WebSocketDisconnect:
#         websocket_manager.disconnect(wallet_address)
#     except Exception as e:
#         logger.error(f"WebSocket error for {wallet_address}: {str(e)}")
#         websocket_manager.disconnect(wallet_address)

# Helper to broadcast new trade
async def broadcast_trade(trade: Trade):
    message = {
        "type": "trade_update",
        "trade": {
            "id": trade.id,
            "trade_type": trade.trade_type,
            "amount_sol": trade.amount_sol_in or trade.amount_sol_out or 0,
            "token_symbol": trade.token_symbol or "Unknown",
            "timestamp": trade.created_at.isoformat() if trade.created_at else None,
        }
    }
    await websocket_manager.send_personal_message(json.dumps(message), trade.user_wallet_address)
        

# gRPC Channel
def create_grpc_channel(endpoint: str, token: str) -> grpc.aio.Channel:
    endpoint = endpoint.replace('http://', '').replace('https://', '')
    logging.info(f"Creating gRPC channel to {endpoint} with token: {token[:8]}...")
    auth_creds = grpc.metadata_call_credentials(
        lambda context, callback: callback((("x-token", token),), None)
    )
    ssl_creds = grpc.ssl_channel_credentials()
    options = (
        ('grpc.ssl_target_name_override', endpoint.split(':')[0]),
        ('grpc.default_authority', endpoint.split(':')[0]),
        ('grpc.keepalive_time_ms', 10000),
        ('grpc.keepalive_timeout_ms', 5000),
        ('grpc.keepalive_permit_without_calls', 1),
    )
    combined_creds = grpc.composite_channel_credentials(ssl_creds, auth_creds)
    channel = grpc.aio.secure_channel(endpoint, combined_creds, options=options)
    logging.info(f"gRPC channel created: {endpoint}")
    return channel

async def raydium_grpc_subscription_loop():
    program_id = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
    create_pool_fee_account = "7YttLkHDoNj9wyDur5pM1ejNaAvT9X4eqaYcHQqtj2G5"
    grpc_url = os.getenv("GRPC_URL", "grpc.ams.shyft.to:443")
    grpc_token = os.getenv("GRPC_TOKEN", "30c7ef87-5bf0-4d70-be9f-3ea432922437")

    while True:
        channel = None
        try:
            # Only log connection attempts, not every loop iteration
            logger.info(f"Starting Raydium gRPC loop with URL: {grpc_url}")
            channel = create_grpc_channel(grpc_url, grpc_token)
            stub = GeyserStub(channel)

            subscribe_request = SubscribeRequest(
                transactions={
                    "raydium_pools": {
                        "vote": False,
                        "failed": False,
                        "account_include": [program_id, create_pool_fee_account],
                    }
                },
                commitment=CommitmentLevel.CONFIRMED,
            )

            # Remove the 30-second status logging
            async for response in stub.Subscribe(iter([subscribe_request])):
                # Only process transaction updates
                if not response.HasField('transaction'):
                    continue

                tx_info = response.transaction
                
                # Get signature from the nested transaction
                signature = None
                if (hasattr(tx_info, 'transaction') and tx_info.transaction and
                    hasattr(tx_info.transaction, 'signature') and tx_info.transaction.signature):
                    signature_bytes = tx_info.transaction.signature
                    signature = base58.b58encode(signature_bytes).decode()
                else:
                    continue

                # Get slot information
                slot = getattr(tx_info, 'slot', 0)

                # Extract account keys
                accounts = []
                try:
                    if (hasattr(tx_info, 'transaction') and tx_info.transaction and
                        hasattr(tx_info.transaction, 'transaction') and tx_info.transaction.transaction and
                        hasattr(tx_info.transaction.transaction, 'message') and tx_info.transaction.transaction.message and
                        hasattr(tx_info.transaction.transaction.message, 'account_keys')):
                        
                        account_keys = tx_info.transaction.transaction.message.account_keys
                        accounts = [base58.b58encode(key).decode() for key in account_keys]
                        
                        # Check if Raydium program is in accounts
                        if program_id in accounts:
                            # Look for Raydium pool creation instructions
                            pool_infos = await find_raydium_pool_creations(tx_info, accounts, signature, slot)
                            
                            if pool_infos:
                                # Only log when pools are actually found and processed
                                logger.info(f"🎯 New pool creation detected! Processing {len(pool_infos)} pool(s)")
                                await process_pool_creations(pool_infos)
                            
                    else:
                        continue
                            
                except Exception as e:
                    # Only log errors, not every extraction attempt
                    logger.error(f"Error extracting account keys: {e}")
                    continue

        except grpc.aio.AioRpcError as e:
            logger.error("gRPC error in Raydium loop: %s - %s", e.code(), e.details())
            await asyncio.sleep(10)
        except Exception as e:
            logger.error("Unexpected error in Raydium gRPC loop: %s", e)
            await asyncio.sleep(10)
        finally:
            if channel is not None:
                await channel.close()
            # Don't log every retry, only log if there was an actual issue
            await asyncio.sleep(10)

async def find_raydium_pool_creations(tx_info, accounts, signature, slot):
    """Extract Raydium pool creation information from transaction"""
    program_id = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
    pool_infos = []
    
    try:
        # Check if Raydium program is in the accounts
        if program_id not in accounts:
            return pool_infos

        # Get instructions from the transaction
        instructions = []
        main_instructions = []
        
        # Main instructions
        if (hasattr(tx_info, 'transaction') and tx_info.transaction and
            hasattr(tx_info.transaction, 'transaction') and tx_info.transaction.transaction and
            hasattr(tx_info.transaction.transaction, 'message') and tx_info.transaction.transaction.message and
            hasattr(tx_info.transaction.transaction.message, 'instructions')):
            
            main_instructions = tx_info.transaction.transaction.message.instructions
            instructions.extend(main_instructions)

        # Inner instructions from meta
        if (hasattr(tx_info, 'transaction') and tx_info.transaction and
            hasattr(tx_info.transaction, 'meta') and tx_info.transaction.meta and
            hasattr(tx_info.transaction.meta, 'inner_instructions')):
            
            for inner_instr in tx_info.transaction.meta.inner_instructions:
                if hasattr(inner_instr, 'instructions'):
                    inner_instructions = inner_instr.instructions
                    instructions.extend(inner_instructions)

        pool_creation_count = 0
        
        # Define Raydium instruction opcodes
        raydium_opcodes = {
            1: "Initialize2 (Pool Creation)",
            2: "Initialize (Legacy Pool Creation)",
            # ... other opcodes
        }
        
        for i, instruction in enumerate(instructions):
            try:
                # Check program ID index bounds
                if instruction.program_id_index >= len(accounts):
                    continue
                    
                instruction_program = accounts[instruction.program_id_index]
                
                if instruction_program != program_id:
                    continue
                
                # Check if this is initialize2 (pool creation) - opcode 1
                if (hasattr(instruction, 'data') and instruction.data and 
                    len(instruction.data) > 0):
                    
                    opcode = instruction.data[0]
                    
                    if opcode == 1:  # Pool creation
                        pool_creation_count += 1
                        
                        # Validate account indices
                        if len(instruction.accounts) < 17:
                            continue
                            
                        pool_id = accounts[instruction.accounts[4]]
                        
                        # Create pool info
                        pool_info = {
                            "updateTime": datetime.utcnow().timestamp(),
                            "slot": slot,
                            "txid": signature,
                            "poolInfos": [{
                                "id": pool_id,
                                "baseMint": accounts[instruction.accounts[8]],
                                "quoteMint": accounts[instruction.accounts[9]],
                                "lpMint": accounts[instruction.accounts[7]],
                                "version": 4,
                                "programId": program_id,
                                "authority": accounts[instruction.accounts[5]],
                                "openOrders": accounts[instruction.accounts[6]],
                                "targetOrders": accounts[instruction.accounts[12]],
                                "baseVault": accounts[instruction.accounts[10]],
                                "quoteVault": accounts[instruction.accounts[11]],
                                "marketId": accounts[instruction.accounts[16]],
                            }]
                        }
                        pool_infos.append(pool_info)
                    
            except Exception as e:
                # Only log actual errors, not routine processing issues
                continue
        
        # Only log if we actually found pools
        if pool_creation_count > 0:
            logger.info(f"Found {pool_creation_count} pool creation instruction(s) in transaction {signature}")
                
    except Exception as e:
        logger.error(f"Error finding Raydium pools: {e}")
        traceback.print_exc()
        
    return pool_infos

async def process_pool_creations(pool_infos):
    """Process and store new pool creations"""
    async with AsyncSessionLocal() as db_session:
        try:
            pools_saved = 0
            
            for pool in pool_infos:
                pool_data = pool["poolInfos"][0]
                
                # Check if this pool already exists in database to avoid duplicates
                existing_stmt = select(NewTokens).where(NewTokens.pool_id == pool_data["id"])
                existing_result = await db_session.execute(existing_stmt)
                existing_pool = existing_result.scalar_one_or_none()
                
                if existing_pool:
                    continue  # Skip if pool already exists

                # Fetch token decimals
                try:
                    async with AsyncClient(settings.SOLANA_RPC_URL) as solana_client:
                        base_mint_acc, quote_mint_acc = await solana_client.get_multiple_accounts([
                            Pubkey.from_string(pool_data["baseMint"]),
                            Pubkey.from_string(pool_data["quoteMint"]),
                        ])

                        if base_mint_acc.value and quote_mint_acc.value:
                            base_decimals = base_mint_acc.value.data[44] if len(base_mint_acc.value.data) > 44 else 9
                            quote_decimals = quote_mint_acc.value.data[44] if len(quote_mint_acc.value.data) > 44 else 6
                            
                            pool_data["baseDecimals"] = base_decimals
                            pool_data["quoteDecimals"] = quote_decimals
                            pool_data["lpDecimals"] = base_decimals
                
                except Exception as e:
                    pool_data["baseDecimals"] = 9
                    pool_data["quoteDecimals"] = 6
                    pool_data["lpDecimals"] = 9

                # Save to database
                token_trade = NewTokens(
                    mint_address=pool_data["baseMint"],
                    pool_id=pool_data["id"],
                    timestamp=datetime.utcnow(),
                    signature=pool["txid"],
                    tx_type="raydium_pool_create",
                    metadata_status="pending"
                )
                db_session.add(token_trade)
                pools_saved += 1

            if pools_saved > 0:
                await db_session.commit()
                logger.info(f"✅ Successfully saved {pools_saved} new pool(s) to database")
                
                # Notify WebSocket clients
                for wallet in websocket_manager.active_connections:
                    for pool in pool_infos:
                        await websocket_manager.send_personal_message(
                            json.dumps({
                                "type": "new_pool",
                                "pool": pool["poolInfos"][0]
                            }),
                            wallet
                        )

                # Process additional token logic for new pools only
                for pool in pool_infos:
                    await process_token_logic(pool["poolInfos"][0]["baseMint"], db_session)
            else:
                logger.info("No new pools to save (all already exist in database)")

        except Exception as e:
            logger.error("Error processing pool creations: %s", e)
            await db_session.rollback()

# Add this function to track Raydium transaction types
async def track_raydium_transaction_types(signature, accounts, instructions):
    """Track and log the types of Raydium transactions we're seeing"""
    program_id = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
    
    if program_id not in accounts:
        return
    
    raydium_instructions = []
    for instruction in instructions:
        try:
            if (hasattr(instruction, 'program_id_index') and 
                instruction.program_id_index < len(accounts) and
                accounts[instruction.program_id_index] == program_id and
                hasattr(instruction, 'data') and instruction.data and len(instruction.data) > 0):
                
                opcode = instruction.data[0]
                raydium_instructions.append(opcode)
        except:
            continue
    
    if raydium_instructions:
        logger.info(f"Raydium transaction {signature} has opcodes: {raydium_instructions}")

def analyze_transaction_type(accounts):
    """Quick analysis of transaction type based on accounts"""
    common_programs = {
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA": "Token Program",
        "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL": "Associated Token Program",
        "11111111111111111111111111111111": "System Program",
        "ComputeBudget111111111111111111111111111111": "Compute Budget Program",
        "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium AMM V4",
        "srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX": "OpenBook DEX",
    }
    
    found_programs = []
    for account in accounts:
        if account in common_programs:
            found_programs.append(common_programs[account])
    
    return found_programs

# Metadata Enrichment
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def process_token_logic(mint: str, db: AsyncSession):
    try:
        logger.info(f"Enriching metadata for: {mint}")
        stmt = select(TokenMetadata).where(TokenMetadata.mint_address == mint)
        result = await db.execute(stmt)
        token = result.scalars().first()
        if not token:
            token = TokenMetadata(mint_address=mint)
            db.add(token)

        cache_key = f"token_metadata:{mint}"
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            token.__dict__.update(json.loads(cached_data))
            await db.merge(token)
            await db.commit()
            return

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
            token.socials_present = bool(dex_data.get("twitter") or dex_data.get("telegram") or dex_data.get("websites"))

        if token.pair_address:
            raydium_data = await get_raydium_pool_info(token.pair_address)
            if raydium_data:
                token.liquidity_burnt = raydium_data.get("burnPercent", 0) == 100
                token.liquidity_pool_size_sol = raydium_data.get("tvl")

        solscan_data = await get_solscan_token_meta(mint)
        if solscan_data:
            token.immutable_metadata = solscan_data.get("is_mutable") is False
            token.mint_authority_renounced = solscan_data.get("mint_authority") is None
            token.freeze_authority_revoked = solscan_data.get("freeze_authority") is None
            token.token_decimals = solscan_data.get("decimals")
            token.holder = solscan_data.get("holder")

        webacy_data = await check_webacy_risk(mint)
        if webacy_data:
            token.webacy_risk_score = webacy_data["risk_score"]
            token.webacy_risk_level = webacy_data["risk_level"]
            token.webacy_moon_potential = webacy_data["moon_potential"]

        token.top10_holders_percentage = await get_top_holders_info(mint)
        token.last_checked_at = datetime.utcnow()

        await db.merge(token)
        await db.commit()

        await redis_client.setex(cache_key, 3600, json.dumps(token.__dict__))
        logger.info(f"Metadata enriched for: {mint}")
    except Exception as e:
        logger.error(f"Error enriching metadata for {mint}: {e}")
        await db.rollback()
        raise

# Filters for 80% Profitability
async def apply_user_filters(user: User, token_meta: TokenMetadata, db: AsyncSession, websocket_manager: ConnectionManager) -> bool:
    async def log_failure(filter_name: str):
        logger.debug(f"Token {token_meta.mint_address} failed {filter_name} for {user.wallet_address}.")
        await websocket_manager.send_personal_message(
            json.dumps({"type": "log", "message": f"Token {token_meta.token_symbol or token_meta.mint_address} failed {filter_name} filter.", "status": "info"}),
            user.wallet_address
        )

    filters = [
        ("Socials Added", user.filter_socials_added, lambda: not token_meta.socials_present),
        ("Liquidity Burnt", user.filter_liquidity_burnt, lambda: not token_meta.liquidity_burnt),
        ("Immutable Metadata", user.filter_immutable_metadata, lambda: not token_meta.immutable_metadata),
        ("Mint Authority Renounced", user.filter_mint_authority_renounced, lambda: not token_meta.mint_authority_renounced),
        ("Freeze Authority Revoked", user.filter_freeze_authority_revoked, lambda: not token_meta.freeze_authority_revoked),
        (
            f"Insufficient Liquidity Pool Size (min {user.filter_check_pool_size_min_sol} SOL)",
            user.filter_check_pool_size_min_sol,
            lambda: token_meta.liquidity_pool_size_sol is None or token_meta.liquidity_pool_size_sol < user.filter_check_pool_size_min_sol
        ),
        (
            "Token Age (15m-72h)",
            True,
            lambda: not token_meta.pair_created_at or (
                (age := datetime.utcnow() - datetime.utcfromtimestamp(token_meta.pair_created_at)) < timedelta(minutes=15) or
                age > timedelta(hours=72)
            )
        ),
        ("Market Cap (< $30k)", True, lambda: token_meta.market_cap is None or float(token_meta.market_cap) < 30000),
        ("Holder Count (< 20)", True, lambda: token_meta.holder is None or token_meta.holder < 20),
        ("Webacy Risk Score (>50)", True, lambda: token_meta.webacy_risk_score is None or token_meta.webacy_risk_score > 50),
    ]

    if user.is_premium:
        filters.extend([
            (
                f"Top 10 Holders % (>{user.filter_top_holders_max_pct}%)",
                user.filter_top_holders_max_pct,
                lambda: token_meta.top10_holders_percentage and token_meta.top10_holders_percentage > user.filter_top_holders_max_pct
            ),
            (
                f"Safety Check Period (<{user.filter_safety_check_period_seconds}s)",
                user.filter_safety_check_period_seconds and token_meta.pair_created_at,
                lambda: (datetime.utcnow() - datetime.utcfromtimestamp(token_meta.pair_created_at)) < timedelta(seconds=user.filter_safety_check_period_seconds)
            ),
            ("Webacy Moon Potential (<80)", True, lambda: token_meta.webacy_moon_potential is None or token_meta.webacy_moon_potential < 80),
        ])

    for filter_name, condition, check in filters:
        if condition and check():
            await log_failure(filter_name)
            return False

    return True

# Metadata Enrichment Loop
async def metadata_enrichment_loop():
    while True:
        try:
            async with AsyncSessionLocal() as db:
                stmt = select(NewTokens).where(NewTokens.metadata_status == "pending").limit(10)
                result = await db.execute(stmt)
                tokens = result.scalars().all()
                for token in tokens:
                    await process_token_logic(token.mint_address, db)
                    token.metadata_status = "processed"
                    await db.commit()
        except Exception as e:
            logger.error(f"Error in metadata enrichment loop: {e}")
        await asyncio.sleep(30)

# Endpoints
@app.get("/ping")
async def ping():
    logger.info("Ping received.")
    return {"message": "pong", "status": "ok"}

@app.get("/health")
async def health_check():
    try:
        async with AsyncClient(settings.SOLANA_RPC_URL) as client:
            await client.is_connected()
        try:
            channel = create_grpc_channel(
                os.getenv("GRPC_URL", "grpc.mainnet.solana.yellowstone.dev:10000"),
                os.getenv("GRPC_TOKEN", "your-grpc-token")
            )
            stub = GeyserStub(channel)
            await stub.GetVersion(GetVersionRequest())
            grpc_status = "ok"
            await channel.close()
        except Exception as e:
            grpc_status = f"error: {e}"
        return {
            "status": "healthy",
            "database": "ok",
            "solana_rpc": "ok",
            "grpc_raydium": grpc_status,
            "message": "All essential services are operational."
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "message": str(e)}

@app.post("/user/update-rpc")
async def update_user_rpc(
    rpc_data: dict,
    current_user: User = Depends(get_current_user_by_wallet),
    db: AsyncSession = Depends(get_db)
):
    if not current_user.is_premium:
        raise HTTPException(status_code=403, detail="Custom RPC is available only for premium users.")
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

# @app.websocket("/ws/logs/{wallet_address}")
# async def websocket_endpoint(websocket: WebSocket, wallet_address: str, db: AsyncSession = Depends(get_db)):
#     await websocket_manager.connect(websocket, wallet_address)
#     try:
#         while True:
#             data = await websocket.receive_json()
#             if data.get("type") == "signed_transaction":
#                 await handle_signed_transaction(data, wallet_address, db)
#             elif data.get("type") == "settings_update":
#                 await update_bot_settings(data.get("settings"), wallet_address, db)
#     except WebSocketDisconnect:
#         websocket_manager.disconnect(wallet_address)
#     except Exception as e:
#         logger.error(f"WebSocket error for {wallet_address}: {e}")
#         websocket_manager.disconnect(wallet_address)

async def update_bot_settings(settings: dict, wallet_address: str, db: AsyncSession):
    try:
        stmt = select(User).filter(User.wallet_address == wallet_address)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")
        for key, value in settings.items():
            if key == "is_premium" and not user.is_premium:
                continue
            setattr(user, key, value)
        await db.merge(user)
        await db.commit()
        await websocket_manager.send_personal_message(
            json.dumps({"type": "log", "message": "Bot settings updated", "status": "info"}),
            wallet_address
        )
    except Exception as e:
        logger.error(f"Error updating settings for {wallet_address}: {e}")
        await websocket_manager.send_personal_message(
            json.dumps({"type": "log", "message": f"Settings update error: {str(e)}", "status": "error"}),
            wallet_address
        )

async def handle_signed_transaction(data: dict, wallet_address: str, db: AsyncSession):
    try:
        signed_tx_base64 = data.get("signed_tx_base64")
        if not signed_tx_base64:
            raise ValueError("Missing signed transaction")
        async with AsyncClient(settings.SOLANA_RPC_URL) as client:
            signed_tx = VersionedTransaction.from_bytes(base64.b64decode(signed_tx_base64))
            tx_hash = await client.send_raw_transaction(signed_tx)
            logger.info(f"Transaction sent for {wallet_address}: {tx_hash}")
            await websocket_manager.send_personal_message(
                json.dumps({"type": "log", "message": f"Transaction sent: {tx_hash}", "status": "info"}),
                wallet_address
            )
    except Exception as e:
        logger.error(f"Error handling signed transaction for {wallet_address}: {e}")
        await websocket_manager.send_personal_message(
            json.dumps({"type": "log", "message": f"Transaction error: {str(e)}", "status": "error"}),
            wallet_address
        )

@app.get("/wallet/balance/{wallet_address}")
async def get_wallet_balance(wallet_address: str):
    try:
        async with AsyncClient(settings.SOLANA_RPC_URL) as client:
            pubkey = Pubkey.from_string(wallet_address)
            balance_response = await client.get_balance(pubkey)
            lamports = balance_response.value
            sol_balance = lamports / 1_000_000_000
            return {"wallet_address": wallet_address, "sol_balance": sol_balance}
    except Exception as e:
        logger.error(f"Error fetching balance for {wallet_address}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching balance: {str(e)}")




@app.post("/trade/log-trade")
async def log_trade(
    trade_data: LogTradeRequest,
    current_user: User = Depends(get_current_user_by_wallet),
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
        swap_provider=trade_data.swap_provider,
        buy_timestamp=datetime.utcnow() if trade_data.trade_type == "buy" else None,
        sell_timestamp=datetime.utcnow() if trade_data.trade_type == "sell" else None,
    )
    db.add(trade)
    await db.commit()
    await websocket_manager.send_personal_message(
        json.dumps({"type": "log", "message": f"Applied 1% fee ({fee_sol:.6f} SOL) on {trade_data.trade_type} trade.", "status": "info"}),
        current_user.wallet_address
    )
    return {"status": "Trade logged successfully."}

@app.get("/trade/history")
async def get_trade_history(current_user: User = Depends(get_current_user_by_wallet), db: AsyncSession = Depends(get_db)):
    stmt = select(Trade).filter(Trade.user_wallet_address == current_user.wallet_address).order_by(Trade.buy_timestamp.desc())
    result = await db.execute(stmt)
    trades = result.scalars().all()
    return [{
        **trade.__dict__,
        "profit_percentage": ((trade.price_usd_at_trade - trade.buy_price) / trade.buy_price * 100) if trade.trade_type == "sell" and trade.buy_price else 0
    } for trade in trades]

@app.post("/subscribe/premium")
async def subscribe_premium(
    subscription_data: SubscriptionRequest,
    current_user: User = Depends(get_current_user_by_wallet),
    db: AsyncSession = Depends(get_db)
):
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        subscription = stripe.Subscription.create(
            customer={"email": subscription_data.email},
            items=[{"price": settings.STRIPE_PREMIUM_PRICE_ID}],
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
        return {"status": "Subscription activated", "payment_intent": subscription.latest_invoice.payment_intent}
    except Exception as e:
        logger.error(f"Subscription failed: {e}")
        raise HTTPException(status_code=400, detail=f"Subscription failed: {str(e)}")

async def run_user_specific_bot_loop(user_wallet_address: str):
    logger.info(f"Starting bot loop for {user_wallet_address}")
    try:
        async with AsyncSessionLocal() as db:
            user_result = await db.execute(select(User).filter(User.wallet_address == user_wallet_address))
            user = user_result.scalar_one_or_none()
            if not user:
                logger.error(f"User {user_wallet_address} not found.")
                await websocket_manager.send_personal_message(
                    json.dumps({"type": "log", "message": "User not found. Stopping bot.", "status": "error"}),
                    user_wallet_address
                )
                return
            while True:
                recent_time_threshold = datetime.utcnow() - timedelta(minutes=30)
                stmt = select(TokenMetadata).filter(TokenMetadata.last_checked_at >= recent_time_threshold).order_by(TokenMetadata.last_checked_at.desc()).limit(10)
                result = await db.execute(stmt)
                tokens = result.scalars().all()
                tasks = [
                    apply_user_filters_and_trade(user, token, db, websocket_manager)
                    for token in tokens
                    if not await redis_client.exists(f"trade:{user_wallet_address}:{token.mint_address}")
                ]
                await asyncio.gather(*tasks)
                await asyncio.sleep(user.bot_check_interval_seconds or 10)
    except asyncio.CancelledError:
        logger.info(f"Bot task for {user_wallet_address} cancelled.")
    except Exception as e:
        logger.error(f"Error in bot loop for {user_wallet_address}: {e}")
        await websocket_manager.send_personal_message(
            json.dumps({"type": "log", "message": f"Bot error: {str(e)}", "status": "error"}),
            user_wallet_address
        )
    finally:
        if user_wallet_address in active_bot_tasks:
            del active_bot_tasks[user_wallet_address]
        logger.info(f"Bot loop for {user_wallet_address} ended.")

async def apply_user_filters_and_trade(user: User, token: TokenMetadata, db: AsyncSession, websocket_manager: ConnectionManager):
    trade_stmt = select(Trade).filter(
        Trade.user_wallet_address == user.wallet_address,
        Trade.mint_address == token.mint_address
    )
    trade_result = await db.execute(trade_stmt)
    if trade_result.scalar_one_or_none():
        return
    if await apply_user_filters(user, token, db, websocket_manager):
        await redis_client.setex(f"trade:{user.wallet_address}:{token.mint_address}", 3600, "processed")
        await execute_user_trade(
            user_wallet_address=user.wallet_address,
            mint_address=token.mint_address,
            amount_sol=user.buy_amount_sol,
            trade_type="buy",
            slippage=user.buy_slippage_bps / 10000.0,
            take_profit=user.sell_take_profit_pct,
            stop_loss=user.sell_stop_loss_pct,
            timeout_seconds=user.sell_timeout_seconds,
            trailing_stop_loss_pct=user.trailing_stop_loss_pct,
            db=db,
            websocket_manager=websocket_manager
        )

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
    if not user:
        raise ValueError("User not found")
    rpc_url = user.custom_rpc_https if user.is_premium and user.custom_rpc_https else settings.SOLANA_RPC_URL
    async with AsyncClient(rpc_url) as client:
        try:
            encrypted_private_key = user.encrypted_private_key.encode()
            private_key_bytes = decrypt_private_key_backend(encrypted_private_key)
            keypair = Keypair.from_bytes(private_key_bytes)
            jupiter = Jupiter(client, keypair)
            quote = await jupiter.get_quote(
                input_mint="So11111111111111111111111111111111111111112" if trade_type == "buy" else mint_address,
                output_mint=mint_address if trade_type == "buy" else "So11111111111111111111111111111111111111112",
                amount=int(amount_sol * 1_000_000_000),
                slippage_bps=int(slippage * 10000)
            )
            recent_fees = await client.get_recent_prioritization_fees()
            priority_fee = max(fee.micro_lamports for fee in recent_fees.value) if recent_fees.value else 100_000
            swap_transaction = await jupiter.swap(
                quote=quote,
                user_public_key=Pubkey.from_string(user_wallet_address),
                priority_fee_micro_lamports=priority_fee
            )
            raw_tx = base64.b64encode(swap_transaction.serialize()).decode()
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
                "raw_tx_base64": raw_tx,
                "last_valid_block_height": quote["last_valid_block_height"],
                "message": f"Execute {trade_type} trade for {mint_address}."
            }
            await websocket_manager.send_personal_message(
                json.dumps(trade_instruction_message),
                user_wallet_address
            )
            if trade_type == "buy":
                asyncio.create_task(monitor_trade_for_sell(
                    user_wallet_address, mint_address, take_profit, stop_loss, timeout_seconds, trailing_stop_loss_pct, db, websocket_manager
                ))
        except Exception as e:
            logger.error(f"Error executing trade for {user_wallet_address}: {e}")
            await websocket_manager.send_personal_message(
                json.dumps({"type": "log", "message": f"Trade error: {str(e)}", "status": "error"}),
                user_wallet_address
            )

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
            if timeout_seconds and (datetime.utcnow() - start_time).total_seconds() > timeout_seconds:
                await execute_user_trade(
                    user_wallet_address, mint_address, trade.amount_tokens, "sell", 0.05, None, None, None, None, db, websocket_manager
                )
                await websocket_manager.send_personal_message(
                    json.dumps({"type": "log", "message": f"Selling {mint_address} due to timeout.", "status": "info"}),
                    user_wallet_address
                )
                break
            if trailing_stop_loss_pct and current_price > (highest_price or buy_price):
                highest_price = current_price
                stop_loss = highest_price * (1 - trailing_stop_loss_pct / 100)
            if take_profit and current_price >= buy_price * (1 + take_profit / 100):
                await execute_user_trade(
                    user_wallet_address, mint_address, trade.amount_tokens, "sell", 0.05, None, None, None, None, db, websocket_manager
                )
                await websocket_manager.send_personal_message(
                    json.dumps({"type": "log", "message": f"Selling {mint_address} at take-profit.", "status": "info"}),
                    user_wallet_address
                )
                break
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
            
            
            