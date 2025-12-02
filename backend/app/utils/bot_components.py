# bot_components.py — ULTRA API VERSION (Dec 2, 2025: Jupiter Ultra API + Referral)
import logging
import json
import base64
import asyncio
from datetime import datetime
from typing import Dict, Optional, Any
import redis.asyncio as redis
import aiohttp
import httpx
from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.signature import Signature
from solders.message import to_bytes_versioned
from solana.rpc.async_api import AsyncClient
from spl.token.instructions import get_associated_token_address
from app.models import Trade, User, TokenMetadata
from app.utils.dexscreener_api import get_dexscreener_data
from app.config import settings
from app.security import decrypt_private_key_backend

logger = logging.getLogger(__name__)

# Redis
redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, wallet_address: str):
        await websocket.accept()
        self.active_connections[wallet_address] = websocket

    def disconnect(self, wallet_address: str):
        self.active_connections.pop(wallet_address, None)

    async def send_personal_message(self, message: str, wallet_address: str):
        ws = self.active_connections.get(wallet_address)
        if ws:
            try:
                await ws.send_text(message)
            except:
                self.disconnect(wallet_address)

websocket_manager = ConnectionManager()


# ===================================================================
# Correct Jupiter Referral ATA (2025)
# ===================================================================
def get_jupiter_referral_ata(referral_pda: str, mint: str) -> str:
    owner = Pubkey.from_string(referral_pda)
    mint_pubkey = Pubkey.from_string(mint)
    ata = get_associated_token_address(owner, mint_pubkey)
    return str(ata)


# ===================================================================
# Non-blocking transaction confirmation
# ===================================================================
async def _confirm_tx_async(rpc_url: str, signature: str, label: str, wallet_address: str, input_sol: float):
    try:
        async with AsyncClient(rpc_url) as client:
            sig = Signature.from_string(signature)
            resp = await client.confirm_transaction(sig, commitment="confirmed")
            statuses = resp.value
            if statuses and len(statuses) > 0 and statuses[0].err:
                err = statuses[0].err
                err_str = str(err)
                error_type = "UNKNOWN"
                if "6025" in err_str:
                    error_type = "INSUFFICIENT_INPUT_LIQUIDITY"
                    user_msg = json.dumps({
                        "type": "log",
                        "message": f"{label} failed: Low liquidity (error 6025). Input {input_sol} SOL too small — try 0.1+ SOL.",
                        "status": "warning",
                        "tx": f"https://solscan.io/tx/{signature}"
                    })
                    await websocket_manager.send_personal_message(user_msg, wallet_address)
                logger.warning(f"{label} {signature} failed on-chain ({error_type}): {err}")
            else:
                logger.info(f"{label} {signature} CONFIRMED")
    except Exception as e:
        logger.warning(f"Confirmation failed for {signature}: {e}")


# ===================================================================
# JUPITER ULTRA API IMPLEMENTATION (CORRECT 2025)
# ===================================================================

async def execute_jupiter_swap(
    user: User,
    input_mint: str,
    output_mint: str,
    amount: int,
    slippage_bps: int,
    label: str = "swap",
    max_retries: int = 3,
) -> dict:

    input_sol = amount / 1_000_000_000.0
    
    # FIX: Ensure MIN_BUY_SOL is a float
    min_buy_sol_str = getattr(settings, 'MIN_BUY_SOL', '0.05')
    try:
        min_buy_sol = float(min_buy_sol_str)
    except (ValueError, TypeError):
        min_buy_sol = 0.05  # Default fallback
    
    # Min buy checks - FIXED: Compare floats properly
    if label == "BUY" and not user.is_premium:
        min_for_free = max(min_buy_sol, 0.01)
        if input_sol < min_for_free:
            raise Exception(f"Free users need min {min_for_free:.2f} SOL for buys. Current: {input_sol:.4f} SOL")
    
    if label == "BUY" and input_sol < min_buy_sol:
        raise Exception(f"Min input too low: {input_sol:.4f} SOL < {min_buy_sol:.2f} SOL")

    user_pubkey = str(user.wallet_address)
    private_key_bytes = decrypt_private_key_backend(user.encrypted_private_key)
    keypair = Keypair.from_bytes(private_key_bytes)

    # Referral fee account (OPTIONAL - skip if not initialized)
    use_referral = True
    fee_account = None
    referral_fee = "0"  # Default no referral
    
    try:
        if hasattr(settings, "JUPITER_REFERRAL_ACCOUNT") and settings.JUPITER_REFERRAL_ACCOUNT:
            fee_mint = output_mint if label == "BUY" else input_mint
            fee_account = get_jupiter_referral_ata(settings.JUPITER_REFERRAL_ACCOUNT, fee_mint)
            referral_fee = "100"  # 1% referral fee in bps
        else:
            use_referral = False
            logger.info(f"No referral account configured, skipping referral fees")
    except Exception as e:
        logger.warning(f"Failed to setup referral account: {e}. Skipping referral...")
        use_referral = False

    # REQUIRED: Jupiter API Key for Ultra API
    if not getattr(settings, "JUPITER_API_KEY", None):
        raise Exception("JUPITER_API_KEY is required for Ultra API. Get one from portal.jup.ag")
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": settings.JUPITER_API_KEY
    }

    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as session:
                base = "https://api.jup.ag/ultra/v1"
                
                # =============================================================
                # 1. GET ORDER (Quote + Transaction)
                # =============================================================
                order_params = {
                    "inputMint": input_mint,
                    "outputMint": output_mint,
                    "amount": str(amount),
                    "slippageBps": str(slippage_bps),
                    "taker": user_pubkey,
                }
                
                # Only add referral if we're using it
                if use_referral and fee_account:
                    order_params["referralAccount"] = fee_account
                    order_params["referralFee"] = referral_fee
                    logger.info(f"Using referral account: {fee_account[:8]}...")
                else:
                    logger.info(f"No referral account, proceeding without referral fees")
                
                logger.info(f"Getting order for {label}: {input_mint[:8]}... → {output_mint[:8]}...")
                
                order_resp = await session.get(f"{base}/order", params=order_params)
                if order_resp.status != 200:
                    txt = await order_resp.text()
                    
                    # Check if it's a referral initialization error
                    if "referralAccount is initialized" in txt:
                        logger.warning(f"Referral account not initialized for token {output_mint[:8]}...")
                        
                        # Try again without referral on the first attempt
                        if attempt == 0 and use_referral:
                            logger.info("Retrying without referral account...")
                            use_referral = False
                            continue  # Retry immediately without referral
                        else:
                            logger.error(f"Order failed: Status {order_resp.status}, Response: {txt[:500]}")
                            raise Exception(f"Order failed: {txt[:200]}")
                    
                    logger.error(f"Order failed: Status {order_resp.status}, Response: {txt[:500]}")
                    
                    # Parse Jupiter error messages
                    try:
                        error_data = json.loads(txt)
                        if "errorMessage" in error_data:
                            raise Exception(f"Jupiter order failed: {error_data['errorMessage']}")
                    except:
                        pass
                    
                    raise Exception(f"Order failed (attempt {attempt+1}): {txt[:300]}")
                
                order_data = await order_resp.json()
                
                # Validate order response
                if "transaction" not in order_data:
                    logger.error(f"No transaction in order response: {order_data}")
                    raise Exception("Jupiter didn't return a transaction")
                
                if "requestId" not in order_data:
                    logger.error(f"No requestId in order response: {order_data}")
                    raise Exception("Jupiter didn't return a requestId")
                
                if "outAmount" not in order_data or int(order_data["outAmount"]) <= 0:
                    logger.error(f"Invalid output amount: {order_data.get('outAmount', 'missing')}")
                    raise Exception("Order returned 0 output - insufficient liquidity")
                
                # Parse platform fee from Ultra API response
                platform_fee_amount = 0
                if "feeBps" in order_data and "feeMint" in order_data:
                    # Ultra API has different fee structure
                    fee_bps = int(order_data.get("feeBps", 0))
                    if fee_bps > 0 and order_data.get("feeMint"):
                        # Estimate fee amount
                        in_amount = int(order_data["inAmount"])
                        platform_fee_amount = (in_amount * fee_bps) // 10000
                
                logger.info(f"{label} order: {int(order_data['inAmount'])/1e9:.4f} SOL → {int(order_data['outAmount'])} tokens | Slippage: {order_data.get('slippageBps', '?')}bps | Referral: {'Yes' if use_referral else 'No'}")
                
                # =============================================================
                # 2. SIGN TRANSACTION
                # =============================================================
                tx_buf = base64.b64decode(order_data["transaction"])
                original_tx = VersionedTransaction.from_bytes(tx_buf)
                message_bytes = to_bytes_versioned(original_tx.message)
                user_signature = keypair.sign_message(message_bytes)
                
                # Create signed transaction
                signed_tx = VersionedTransaction.populate(original_tx.message, [user_signature])
                raw_tx = bytes(signed_tx)
                signed_transaction_base64 = base64.b64encode(raw_tx).decode("utf-8")
                
                # =============================================================
                # 3. EXECUTE ORDER (Jupiter sends the transaction)
                # =============================================================
                execute_payload = {
                    "signedTransaction": signed_transaction_base64,
                    "requestId": order_data["requestId"]
                }
                
                execute_resp = await session.post(f"{base}/execute", json=execute_payload)
                if execute_resp.status != 200:
                    txt = await execute_resp.text()
                    logger.error(f"Execute failed: Status {execute_resp.status}, Response: {txt[:500]}")
                    raise Exception(f"Execute failed (attempt {attempt+1}): {txt[:300]}")
                
                execute_data = await execute_resp.json()
                
                # Check execution status
                if execute_data.get("status") == "Success":
                    signature = execute_data.get("signature")
                    if not signature:
                        raise Exception("Execute succeeded but no signature returned")
                    
                    logger.info(f"{label} SUCCESS → https://solscan.io/tx/{signature}")
                    
                    # Log success details
                    input_amount_result = execute_data.get("inputAmountResult", order_data["inAmount"])
                    output_amount_result = execute_data.get("outputAmountResult", order_data["outAmount"])
                    
                    logger.info(f"{label} executed: {int(input_amount_result)/1e9:.4f} SOL → {int(output_amount_result)} tokens")
                    
                    # Fire-and-forget confirmation
                    rpc_url = user.custom_rpc_https or settings.SOLANA_RPC_URL
                    asyncio.create_task(_confirm_tx_async(rpc_url, signature, label, user_pubkey, input_sol))
                    
                    return {
                        "raw_tx_base64": signed_transaction_base64,
                        "signature": signature,
                        "out_amount": int(output_amount_result),
                        "in_amount": int(input_amount_result),
                        "estimated_referral_fee": platform_fee_amount,
                        "fee_applied": platform_fee_amount > 0 and use_referral,
                        "method": "jup_ultra_referral",
                        "status": "success",
                        "request_id": order_data["requestId"],
                        "referral_used": use_referral
                    }
                
                else:
                    # Execution failed
                    status = execute_data.get("status", "Unknown")
                    error_code = execute_data.get("code", -1)
                    signature = execute_data.get("signature")
                    
                    # Map error codes to user-friendly messages
                    error_messages = {
                        -1: "Missing cached order (requestId expired)",
                        -2: "Invalid signed transaction",
                        -3: "Invalid message bytes",
                        -4: "Missing request ID",
                        -5: "Missing signed transaction",
                        -1000: "Failed to land transaction",
                        -1001: "Unknown error",
                        -1002: "Invalid transaction",
                        -1003: "Transaction not fully signed",
                        -1004: "Invalid block height",
                        -1005: "Transaction expired",
                        -1006: "Transaction timed out",
                        -1007: "Gasless unsupported wallet"
                    }
                    
                    error_msg = error_messages.get(error_code, f"Error code: {error_code}")
                    
                    if signature:
                        logger.warning(f"{label} EXECUTE FAILED ({status}): {error_msg} | Tx: https://solscan.io/tx/{signature}")
                        raise Exception(f"{label} failed: {error_msg}")
                    else:
                        logger.warning(f"{label} EXECUTE FAILED ({status}): {error_msg}")
                        raise Exception(f"{label} failed: {error_msg}")
        
        except Exception as e:
            error_str = str(e)
            
            # Log specific error types
            if "6025" in error_str or "InsufficientInputAmountWithSlippage" in error_str:
                logger.warning(f"{label} FAILED → Low liquidity (6025) | Input: {input_sol:.4f} SOL")
                
                # Send user-friendly message
                if not user.is_premium and label == "BUY":
                    user_msg = json.dumps({
                        "type": "log",
                        "message": f"⚠️ Buy failed: Low liquidity (error 6025). Try increasing buy amount to 0.2+ SOL.",
                        "status": "warning"
                    })
                    await websocket_manager.send_personal_message(user_msg, user.wallet_address)
            
            elif "insufficient liquidity" in error_str.lower():
                logger.warning(f"{label} FAILED → Insufficient liquidity for {output_mint[:8]}...")
            
            elif "Transaction simulation failed" in error_str:
                # Parse custom program error
                if "custom program error: 0x1789" in error_str:
                    logger.warning(f"{label} FAILED → Jupiter program error 0x1789 (likely slippage/price moved)")
                else:
                    logger.warning(f"{label} FAILED → Transaction simulation failed")
            
            elif "referralAccount is initialized" in error_str:
                logger.warning(f"{label} FAILED → Referral account not initialized. Will retry without referral.")
                # Don't raise exception, let it retry without referral
            
            else:
                logger.warning(f"{label} FAILED (attempt {attempt+1}): {error_str}")
            
            if attempt == max_retries - 1:
                # Final attempt failed
                if "6025" in error_str:
                    raise Exception(f"Low liquidity (6025) after {max_retries} attempts. Try increasing buy amount to 0.2+ SOL.")
                raise e
            
            # Exponential backoff
            wait_time = 2 * (attempt + 1)
            logger.info(f"Retrying {label} in {wait_time}s (attempt {attempt+2}/{max_retries})...")
            await asyncio.sleep(wait_time)

    raise Exception(f"All {max_retries} retries failed for {label}")



# ===================================================================
# BUY LOGIC (Updated for Ultra API)
# ===================================================================

async def execute_user_buy(user: User, token: TokenMetadata, db: AsyncSession, websocket_manager: ConnectionManager):
    mint = token.mint_address
    lock_key = f"buy_lock:{user.wallet_address}:{mint}"
    
    # Check lock
    if await redis_client.get(lock_key):
        logger.info(f"Buy locked for {mint} – skipping")
        return
    
    await redis_client.setex(lock_key, 60, "1")

    try:
        # Get fresh DexScreener data
        dex_data = await get_dexscreener_data(mint)
        
        if not dex_data:
            raise Exception(f"No DexScreener data for {mint[:8]}...")
        
        # DEBUG: Check DexScreener data structure
        logger.info(f"DexScreener data for {mint[:8]}...:")
        logger.info(f"  Keys: {list(dex_data.keys())}")
        if 'raw' in dex_data and 'liquidity' in dex_data['raw']:
            logger.info(f"  Raw liquidity: {dex_data['raw']['liquidity']} (type: {type(dex_data['raw']['liquidity'])})")
        
        # FIX: Handle both old and new DexScreener formats
        liquidity_usd = 0.0
        
        # Check for direct liquidity value (your format shows "liquidity": 74313.95)
        if "liquidity" in dex_data:
            liquidity_value = dex_data["liquidity"]
            logger.info(f"Direct liquidity value: {liquidity_value} (type: {type(liquidity_value)})")
            try:
                if isinstance(liquidity_value, (int, float)):
                    liquidity_usd = float(liquidity_value)
                elif isinstance(liquidity_value, str):
                    liquidity_usd = float(liquidity_value)
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse direct liquidity: {e}")
        
        # Also check for liquidity_usd field (your format shows this too)
        if "liquidity_usd" in dex_data:
            try:
                liquidity_usd = float(dex_data["liquidity_usd"])
                logger.info(f"Using liquidity_usd field: {liquidity_usd}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse liquidity_usd: {e}")
        
        # Also check nested structure (old format)
        elif "liquidity" in dex_data and isinstance(dex_data["liquidity"], dict):
            liquidity_value = dex_data["liquidity"].get("usd", 0)
            try:
                liquidity_usd = float(liquidity_value)
            except (ValueError, TypeError):
                liquidity_usd = 0.0
        
        logger.info(f"Token {mint[:8]}... final liquidity: ${liquidity_usd:.2f}")
        
        # Get token decimals
        decimals = token.token_decimals or 9
        if dex_data and "decimals" in dex_data:
            try:
                decimals = int(dex_data["decimals"])
            except:
                pass
        
        amount_lamports = int(user.buy_amount_sol * 1_000_000_000)
        
        slippage_bps = int(user.buy_slippage_bps) if user.buy_slippage_bps else 500  # Default 5%

        # CAP MAX SLIPPAGE AT 1500 (15%)
        MAX_ALLOWED_SLIPPAGE_BPS = 1500
        if slippage_bps > MAX_ALLOWED_SLIPPAGE_BPS:
            logger.warning(f"Capping slippage from {slippage_bps}bps to {MAX_ALLOWED_SLIPPAGE_BPS}bps (15%) for safety")
            slippage_bps = MAX_ALLOWED_SLIPPAGE_BPS
            
        # Adjust slippage for low liquidity tokens
        if liquidity_usd < 50000.0:  # $50K
            # Cap at 15% for low liquidity tokens
            slippage_bps = min(1500, slippage_bps * 1.5)  # 1.5x slippage but max 15%
            logger.info(f"Low liquidity token (${liquidity_usd:.0f}): Using {slippage_bps}bps slippage ({slippage_bps/100:.1f}%)")
            
        # Send pre-buy message
        await websocket_manager.send_personal_message(json.dumps({
            "type": "log",
            "message": f"🔄 Buying {token.token_symbol or mint[:8]} with {user.buy_amount_sol} SOL...",
            "status": "info"
        }), user.wallet_address)
        
        logger.info(f"Attempting buy: {user.buy_amount_sol} SOL → {mint[:8]}... (liquidity: ${liquidity_usd:.0f}, slippage: {slippage_bps}bps)")
        
        try:
            swap = await execute_jupiter_swap(
                user=user,
                input_mint=settings.SOL_MINT,
                output_mint=mint,
                amount=amount_lamports,
                slippage_bps=slippage_bps,
                label="BUY",
            )
        except Exception as swap_error:
            # Handle Jupiter API errors specifically
            error_msg = str(swap_error)
            if "JUPITER_API_KEY" in error_msg:
                raise Exception("Jupiter API key missing. Please set JUPITER_API_KEY in .env")
            elif "6025" in error_msg:
                raise Exception(f"Low liquidity error. Try increasing buy amount to 0.2+ SOL")
            else:
                raise swap_error

        token_amount = swap["out_amount"] / (10 ** decimals)
        
        if token_amount <= 0:
            raise Exception("Swap returned 0 tokens")

        logger.info(f"Buy successful: {token_amount:.2f} tokens received")
        
        # Use current price from dex_data if available
        current_price = token.price_usd
        if dex_data and dex_data.get("priceUsd"):
            try:
                current_price = float(dex_data["priceUsd"])
            except:
                pass
        
        token_logo = token.token_logo or f"https://dd.dexscreener.com/ds-logo/solana/{mint}.png"
        
        # Create trade record
        trade = Trade(
            user_wallet_address=user.wallet_address,
            mint_address=mint,
            token_symbol=token.token_symbol or mint[:8],
            trade_type="buy",
            amount_sol=user.buy_amount_sol,
            amount_tokens=token_amount,
            price_usd_at_trade=current_price,
            buy_timestamp=datetime.utcnow(),
            take_profit=user.sell_take_profit_pct,
            stop_loss=user.sell_stop_loss_pct,
            token_amounts_purchased=token_amount,
            token_decimals=decimals,
            # I WILL BE ADDING THIS TO MY SCHEMA LATER
            # liquidity_at_buy=liquidity_usd,
            # slippage_bps=slippage_bps
        )
        db.add(trade)
        await db.commit()
        
        # Prepare explorer URLs
        explorer_urls = {
            "solscan": f"https://solscan.io/tx/{swap['signature']}",
            "dexScreener": f"https://dexscreener.com/solana/{mint}",
            "jupiter": f"https://jup.ag/token/{mint}"
        }

        # Send success message
        # await websocket_manager.send_personal_message(json.dumps({
        #     "type": "trade_instruction",
        #     "action": "buy",
        #     "mint": mint,
        #     "amount_sol": user.buy_amount_sol,
        #     "raw_tx_base64": swap["raw_tx_base64"],
        #     "token_amount": round(token_amount, 6),
        #     "price_usd": current_price,
        #     "fee_applied": swap["fee_applied"],
        #     "fee_percentage": 1.0 if swap["fee_applied"] else 0.0,
        #     "signature": swap["signature"],
        #     "solscan_url": f"https://solscan.io/tx/{swap['signature']}",
        #     "liquidity": liquidity_usd
        # }), user.wallet_address)
        
        # Send success message with token logo from database
        await websocket_manager.send_personal_message(json.dumps({
            "type": "trade_update",
            "trade": {
                "id": f"buy-{trade.id}-{datetime.utcnow().timestamp()}",
                "type": "buy",
                "mint_address": mint,
                "token_symbol": token.token_symbol or mint[:8],
                "token_logo": token_logo,  # From database
                "amount_sol": user.buy_amount_sol,
                "amount_tokens": token_amount,
                "tx_hash": swap["signature"],
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "explorer_urls": explorer_urls
            }
        }), user.wallet_address)
        
        # Also send a simple success message
        await websocket_manager.send_personal_message(json.dumps({
            "type": "log",
            "message": f"✅ Buy successful! {token_amount:.2f} tokens at ${current_price:.6f} each",
            "status": "success"
        }), user.wallet_address)
        
        # Send monitoring started message
        await websocket_manager.send_personal_message(json.dumps({
            "type": "log",
            "message": f"📈 Monitoring {token.token_symbol or mint[:8]} for take profit ({user.sell_take_profit_pct}%) or stop loss ({user.sell_stop_loss_pct}%)",
            "status": "info"
        }), user.wallet_address)

        # Start monitoring
        asyncio.create_task(monitor_position(
            user=user, trade=trade, entry_price_usd=current_price,
            token_decimals=decimals, token_amount=token_amount,
            db=db, websocket_manager=websocket_manager
        ))

    except Exception as e:
        logger.error(f"BUY FAILED for {mint}: {e}", exc_info=True)
        error_msg = str(e)
        
        # Provide helpful error messages
        if "6025" in error_msg or "low liquidity" in error_msg.lower():
            user_friendly_msg = f"Buy failed: Low liquidity. Try increasing amount to 0.2+ SOL."
        elif "JUPITER_API_KEY" in error_msg:
            user_friendly_msg = f"Buy failed: Missing Jupiter API key. Check your .env file."
        elif "insufficient" in error_msg.lower():
            user_friendly_msg = f"Buy failed: Insufficient liquidity."
        elif "'>' not supported" in error_msg:
            user_friendly_msg = f"Buy failed: Configuration error (check MIN_BUY_SOL in settings)."
        else:
            user_friendly_msg = f"Buy failed: {error_msg[:100]}"
        
        await websocket_manager.send_personal_message(json.dumps({
            "type": "log", 
            "message": user_friendly_msg, 
            "status": "error"
        }), user.wallet_address)
        
        logger.error(f"Detailed buy error for {mint}: {error_msg}")
    finally:
        await redis_client.delete(lock_key)




# ===================================================================
# MONITOR & SELL (Updated for Ultra API)
# ===================================================================
# async def monitor_position(
#     user: User,
#     trade: Trade,
#     entry_price_usd: float,
#     token_decimals: int,
#     token_amount: float,
#     db: AsyncSession,
#     websocket_manager: ConnectionManager
# ):
#     if token_amount <= 0:
#         logger.warning(f"Invalid token_amount {token_amount} for {trade.mint_address} – skipping monitor")
#         return

#     start = datetime.utcnow()
#     amount_lamports = int(token_amount * (10 ** token_decimals))
#     mint = trade.mint_address
    
#     # Log that monitoring has started
#     logger.info(f"🚀 Starting to monitor {mint[:8]}... for user {user.wallet_address[:8]}...")
#     logger.info(f"  Entry price: ${entry_price_usd:.6f}")
#     logger.info(f"  Token amount: {token_amount:.2f}")
#     logger.info(f"  Take profit: {user.sell_take_profit_pct}%")
#     logger.info(f"  Stop loss: {user.sell_stop_loss_pct}%")
#     logger.info(f"  Timeout: {user.sell_timeout_seconds}s")

#     while True:
#         try:
#             # Check if trade already sold (edge case)
#             db_trade = await db.get(Trade, trade.id)
#             if db_trade and db_trade.sell_timestamp:
#                 logger.info(f"Trade {mint[:8]}... already sold, stopping monitor")
#                 break

#             dex = await get_dexscreener_data(mint)
#             if not dex or not dex.get("priceUsd"):
#                 await asyncio.sleep(5)
#                 continue

#             price = float(dex["priceUsd"])
#             if entry_price_usd <= 0 or price <= 0:
#                 await asyncio.sleep(5)
#                 continue
            
#             pnl = (price / entry_price_usd - 1) * 100
#             logger.debug(f"Monitor {mint[:8]}...: ${price:.6f} | PnL: {pnl:.2f}% | TP: {user.sell_take_profit_pct}% | SL: {user.sell_stop_loss_pct}%")

#             sell_reason = None
#             if user.sell_take_profit_pct and pnl >= user.sell_take_profit_pct:
#                 sell_reason = "TP"
#             elif user.sell_stop_loss_pct and pnl <= -user.sell_stop_loss_pct:
#                 sell_reason = "SL"
#             elif user.sell_timeout_seconds and (datetime.utcnow() - start).total_seconds() > user.sell_timeout_seconds:
#                 sell_reason = "Timeout"

#             if sell_reason:
#                 logger.info(f"Selling {mint[:8]}... - Reason: {sell_reason}, PnL: {pnl:.2f}%")
                
#                 # Update slippage based on current liquidity
#                 slippage_bps = int(user.sell_slippage_bps) if user.sell_slippage_bps else 500  # Default 5%
#                 liquidity_usd = 0.0
#                 if dex and "liquidity" in dex and isinstance(dex["liquidity"], dict):
#                     liquidity_value = dex["liquidity"].get("usd", 0)
#                     try:
#                         liquidity_usd = float(liquidity_value)
#                     except (ValueError, TypeError):
#                         liquidity_usd = 0.0
                
#                 if liquidity_usd < 50000.0:  # Low liquidity
#                     slippage_bps = min(1500, slippage_bps * 3)  # Triple slippage but max 15%
                    
#                 swap = await execute_jupiter_swap(
#                     user=user,
#                     input_mint=mint,
#                     output_mint=settings.SOL_MINT,
#                     amount=amount_lamports,
#                     slippage_bps=slippage_bps,
#                     label="SELL",
#                 )

#                 profit_usd = (price - entry_price_usd) * token_amount
#                 trade.sell_timestamp = datetime.utcnow()
#                 trade.profit_usd = round(profit_usd, 4)
#                 trade.sell_reason = sell_reason
#                 trade.price_usd_at_trade = price
#                 trade.sell_tx_hash = swap.get("signature") 
#                 await db.commit()

#                 await websocket_manager.send_personal_message(json.dumps({
#                     "type": "trade_instruction",
#                     "action": "sell",
#                     "mint": mint,
#                     "reason": sell_reason,
#                     "pnl_pct": round(pnl, 2),
#                     "profit_usd": round(profit_usd, 4),
#                     "raw_tx_base64": swap["raw_tx_base64"],
#                     "fee_applied": swap["fee_applied"],
#                     "fee_percentage": 1.0 if swap["fee_applied"] else 0.0,
#                     "signature": swap["signature"],
#                     "solscan_url": f"https://solscan.io/tx/{swap['signature']}"
#                 }), user.wallet_address)
#                 break

#             await asyncio.sleep(4)
#         except Exception as e:
#             logger.error(f"Monitor error for {mint}: {e}")
#             await asyncio.sleep(10)
            
#             # If monitor fails repeatedly, check if trade still exists
#             try:
#                 db_trade = await db.get(Trade, trade.id)
#                 if not db_trade:
#                     logger.warning(f"Trade {mint[:8]}... no longer in DB, stopping monitor")
#                     break
#             except:
#                 pass
            
            
            
async def monitor_position(
    user: User,
    trade: Trade,
    entry_price_usd: float,
    token_decimals: int,
    token_amount: float,
    db: AsyncSession,
    websocket_manager: ConnectionManager
):
    if token_amount <= 0:
        logger.warning(f"Invalid token_amount {token_amount} for {trade.mint_address} – skipping monitor")
        return

    start = datetime.utcnow()
    amount_lamports = int(token_amount * (10 ** token_decimals))
    mint = trade.mint_address
    
    # Log that monitoring has started
    logger.info(f"🚀 Starting to monitor {mint[:8]}... for user {user.wallet_address[:8]}...")
    logger.info(f"  Entry price: ${entry_price_usd:.6f}")
    logger.info(f"  Token amount: {token_amount:.2f}")
    logger.info(f"  Take profit: {user.sell_take_profit_pct}%")
    logger.info(f"  Stop loss: {user.sell_stop_loss_pct}%")
    logger.info(f"  Timeout: {user.sell_timeout_seconds}s")

    while True:
        try:
            # Check if trade already sold (edge case)
            db_trade = await db.get(Trade, trade.id)
            if db_trade and db_trade.sell_timestamp:
                logger.info(f"Trade {mint[:8]}... already sold, stopping monitor")
                break

            dex = await get_dexscreener_data(mint)
            if not dex or not dex.get("priceUsd"):
                logger.debug(f"No price data for {mint[:8]}... - waiting")
                await asyncio.sleep(5)
                continue

            price = float(dex["priceUsd"])
            if entry_price_usd <= 0 or price <= 0:
                logger.debug(f"Invalid price for {mint[:8]}... - entry: ${entry_price_usd}, current: ${price}")
                await asyncio.sleep(5)
                continue
            
            pnl = (price / entry_price_usd - 1) * 100
            
            # Log PnL every 30 seconds for debugging
            if int(datetime.utcnow().timestamp()) % 30 == 0:  # Every 30 seconds
                logger.info(f"Monitor {mint[:8]}...: ${price:.6f} | PnL: {pnl:.2f}% | TP: {user.sell_take_profit_pct}% | SL: {user.sell_stop_loss_pct}%")
            else:
                logger.debug(f"Monitor {mint[:8]}...: ${price:.6f} | PnL: {pnl:.2f}%")

            sell_reason = None
            if user.sell_take_profit_pct and pnl >= user.sell_take_profit_pct:
                sell_reason = "TP"
                logger.info(f"TAKE PROFIT HIT for {mint[:8]}...: PnL {pnl:.2f}% >= {user.sell_take_profit_pct}%")
            elif user.sell_stop_loss_pct and pnl <= -user.sell_stop_loss_pct:
                sell_reason = "SL"
                logger.info(f"STOP LOSS HIT for {mint[:8]}...: PnL {pnl:.2f}% <= -{user.sell_stop_loss_pct}%")
            elif user.sell_timeout_seconds and (datetime.utcnow() - start).total_seconds() > user.sell_timeout_seconds:
                sell_reason = "Timeout"
                logger.info(f"TIMEOUT for {mint[:8]}...: {(datetime.utcnow() - start).total_seconds():.0f}s > {user.sell_timeout_seconds}s")

            if sell_reason:
                logger.info(f"🚨 SELLING {mint[:8]}... - Reason: {sell_reason}, PnL: {pnl:.2f}%")
                
                # Send sell notification
                await websocket_manager.send_personal_message(json.dumps({
                    "type": "log",
                    "message": f"🚨 Selling {trade.token_symbol or mint[:8]} - {sell_reason} triggered (PnL: {pnl:.2f}%)",
                    "status": "warning"
                }), user.wallet_address)
                
                # Update slippage based on current liquidity
                slippage_bps = int(user.sell_slippage_bps) if user.sell_slippage_bps else 500  # Default 5%
                liquidity_usd = 0.0
                if dex and "liquidity" in dex and isinstance(dex["liquidity"], dict):
                    liquidity_value = dex["liquidity"].get("usd", 0)
                    try:
                        liquidity_usd = float(liquidity_value)
                    except (ValueError, TypeError):
                        liquidity_usd = 0.0
                
                if liquidity_usd < 50000.0:  # Low liquidity
                    slippage_bps = min(1500, slippage_bps * 3)  # Triple slippage but max 15%
                    
                swap = await execute_jupiter_swap(
                    user=user,
                    input_mint=mint,
                    output_mint=settings.SOL_MINT,
                    amount=amount_lamports,
                    slippage_bps=slippage_bps,
                    label="SELL",
                )

                profit_usd = (price - entry_price_usd) * token_amount
                trade.sell_timestamp = datetime.utcnow()
                trade.profit_usd = round(profit_usd, 4)
                trade.sell_reason = sell_reason
                trade.price_usd_at_trade = price
                trade.sell_tx_hash = swap.get("signature") 
                await db.commit()

                await websocket_manager.send_personal_message(json.dumps({
                    "type": "trade_instruction",
                    "action": "sell",
                    "mint": mint,
                    "reason": sell_reason,
                    "pnl_pct": round(pnl, 2),
                    "profit_usd": round(profit_usd, 4),
                    "raw_tx_base64": swap["raw_tx_base64"],
                    "fee_applied": swap["fee_applied"],
                    "fee_percentage": 1.0 if swap["fee_applied"] else 0.0,
                    "signature": swap["signature"],
                    "solscan_url": f"https://solscan.io/tx/{swap['signature']}"
                }), user.wallet_address)
                
                # Send final sell confirmation
                await websocket_manager.send_personal_message(json.dumps({
                    "type": "log",
                    "message": f"✅ Sold {trade.token_symbol or mint[:8]}! Profit: ${profit_usd:.4f} ({pnl:.2f}%)",
                    "status": "success"
                }), user.wallet_address)
                break

            await asyncio.sleep(4)
        except Exception as e:
            logger.error(f"Monitor error for {mint}: {e}")
            await asyncio.sleep(10)
            
            # If monitor fails repeatedly, check if trade still exists
            try:
                db_trade = await db.get(Trade, trade.id)
                if not db_trade:
                    logger.warning(f"Trade {mint[:8]}... no longer in DB, stopping monitor")
                    break
            except:
                pass
            
            
            
                    
            
            