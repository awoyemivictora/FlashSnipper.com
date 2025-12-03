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




async def get_fee_statistics():
    """Get statistics about collected fees"""
    try:
        # Get all fee records
        fee_records = await redis_client.lrange("fee_tracking", 0, -1)
        
        total_fees = 0
        total_transactions = len(fee_records)
        
        for record in fee_records:
            try:
                data = json.loads(record)
                fee_amount = data.get("fee_amount", 0)
                total_fees += fee_amount
            except:
                pass
        
        return {
            "total_transactions": total_transactions,
            "total_fees_collected": total_fees,
            "average_fee_per_tx": total_fees / total_transactions if total_transactions > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Failed to get fee statistics: {e}")
        return {"error": str(e)}

       
async def get_fee_analytics(db: AsyncSession):
    """Get analytics about fee collection"""
    from sqlalchemy import select, func
    from app.models import Trade  # Add this import
    
    # Get total fees collected
    stmt = select(
        func.count(Trade.id).label("total_trades"),
        func.count(Trade.id).filter(Trade.fee_applied == True).label("trades_with_fees"),
        func.coalesce(func.sum(Trade.fee_amount), 0).label("total_fees_collected"),
        func.avg(Trade.fee_percentage).label("avg_fee_percentage")
    )
    
    result = await db.execute(stmt)
    stats = result.first()
    
    # Get fee distribution by mint
    stmt_mint = select(
        Trade.fee_mint,
        func.count(Trade.id).label("count"),
        func.sum(Trade.fee_amount).label("total_amount")
    ).where(
        Trade.fee_applied == True
    ).group_by(
        Trade.fee_mint
    )
    
    result_mint = await db.execute(stmt_mint)
    mint_distribution = result_mint.all()
    
    return {
        "total_trades": stats.total_trades or 0,
        "trades_with_fees": stats.trades_with_fees or 0,
        "total_fees_collected": float(stats.total_fees_collected or 0),
        "avg_fee_percentage": float(stats.avg_fee_percentage or 0),
        "fee_rate": (stats.trades_with_fees or 0) / (stats.total_trades or 1) * 100,
        "mint_distribution": [
            {
                "mint": mint,
                "count": count,
                "total_amount": float(total_amount or 0)
            }
            for mint, count, total_amount in mint_distribution
        ]
    } 
        
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

    # 🔥 CRITICAL FIX: Ultra API fee implementation
    use_referral = True
    referral_fee = "100"  # 1% fee in basis points
    
    # Get the Ultra referral account
    referral_account = getattr(settings, 'JUPITER_REFERRAL_ACCOUNT', None)
    
    if referral_account:
        logger.info(f"💰 Using Ultra referral account: {referral_account[:8]}...")
        logger.info(f"   Applying 1% fee on {label} transaction")
        
        # For Ultra API, we just pass the referral account directly
        # DON'T try to calculate token accounts - Jupiter handles it
        fee_account = referral_account  # Use the referral account directly
    else:
        logger.warning("⚠️ No Ultra referral account configured - missing out on 1% fees!")
        use_referral = False
        fee_account = None

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
                # 1. GET ORDER WITH 1% FEE
                # =============================================================
                order_params = {
                    "inputMint": input_mint,
                    "outputMint": output_mint,
                    "amount": str(amount),
                    "slippageBps": str(slippage_bps),
                    "taker": user_pubkey,
                }
                
                # 🔥 Add referral parameters for Ultra API
                if use_referral and fee_account:
                    order_params["referralAccount"] = fee_account
                    order_params["referralFee"] = referral_fee
                    logger.info(f"💰 Adding 1% fee via Ultra API")
                else:
                    logger.warning("⚠️ Proceeding without 1% fee - you're losing revenue!")
                
                logger.info(f"Getting order for {label}: {input_mint[:8]}... → {output_mint[:8]}...")
                
                order_resp = await session.get(f"{base}/order", params=order_params)
                if order_resp.status != 200:
                    txt = await order_resp.text()
                    
                    # Check if it's a referral initialization error
                    if "referralAccount is initialized" in txt:
                        logger.warning(f"Referral token account not initialized for this swap")
                        
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
                
                # 🔥 CHECK IF 1% FEE IS APPLIED
                fee_applied = False
                fee_amount = 0
                fee_percentage = 0.0
                
                if "feeBps" in order_data:
                    fee_bps = int(order_data.get("feeBps", 0))
                    if fee_bps >= 100:  # At least 1% fee
                        fee_applied = True
                        fee_percentage = fee_bps / 100  # Convert to percentage
                        in_amount = int(order_data["inAmount"])
                        fee_amount = (in_amount * fee_bps) // 10000
                        
                        logger.info(f"💰 1% FEE CONFIRMED: {fee_bps}bps fee applied")
                        
                        # Log fee details
                        fee_mint = order_data.get("feeMint", "Unknown")
                        if "So111" in fee_mint:
                            fee_sol = fee_amount / 1e9
                            logger.info(f"   Estimated fee: {fee_sol:.6f} SOL")
                        elif "EPjFW" in fee_mint:
                            fee_usdc = fee_amount / 1e6
                            logger.info(f"   Estimated fee: {fee_usdc:.6f} USDC")
                        else:
                            logger.info(f"   Estimated fee: {fee_amount} tokens")
                    else:
                        logger.warning(f"⚠️ Fee mismatch: {fee_bps}bps (expected 100bps)")
                
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
                
                logger.info(f"{label} order: {int(order_data['inAmount'])/1e9:.4f} SOL → {int(order_data['outAmount'])} tokens | Slippage: {order_data.get('slippageBps', '?')}bps | 1% Fee: {'✅' if fee_applied else '❌'}")
                
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
                    
                    # 🔥 TRACK FEE IF APPLIED
                    if fee_applied:
                        # Store fee info for analytics
                        await store_fee_info(
                            wallet_address=user.wallet_address,
                            tx_signature=signature,
                            fee_amount=fee_amount,
                            fee_mint=order_data.get("feeMint", "Unknown"),  # This is correct
                            trade_type=label,
                            input_amount=int(input_amount_result),
                            output_amount=int(output_amount_result)
                        )
                    
                    logger.info(f"{label} executed: {int(input_amount_result)/1e9:.4f} SOL → {int(output_amount_result)} tokens | 1% Fee: {'✅' if fee_applied else '❌'}")
                    
                    # Fire-and-forget confirmation
                    rpc_url = user.custom_rpc_https or settings.SOLANA_RPC_URL
                    asyncio.create_task(_confirm_tx_async(rpc_url, signature, label, user_pubkey, input_sol))
                    
                    return {
                        "raw_tx_base64": signed_transaction_base64,
                        "signature": signature,
                        "out_amount": int(output_amount_result),
                        "in_amount": int(input_amount_result),
                        "estimated_referral_fee": fee_amount,
                        "fee_applied": fee_applied,
                        "fee_percentage": fee_percentage,
                        "fee_bps": fee_bps if fee_applied else 0,
                        "fee_mint": order_data.get("feeMint", "") if fee_applied else "",  # Add this line
                        "method": "jup_ultra_referral",
                        "status": "success",
                        "request_id": order_data["requestId"],
                        "referral_used": fee_applied
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
                logger.warning(f"{label} FAILED → Referral token account not initialized. Will retry without referral.")
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


async def store_fee_info(wallet_address: str, tx_signature: str, fee_amount: int, 
                        fee_mint: str, trade_type: str, input_amount: int, output_amount: int):
    """Store fee information in Redis for tracking"""
    try:
        fee_data = {
            "user": wallet_address,
            "tx": tx_signature,
            "fee_amount": fee_amount,
            "fee_mint": fee_mint,
            "trade_type": trade_type,
            "input_amount": input_amount,
            "output_amount": output_amount,
            "timestamp": datetime.utcnow().isoformat(),
            "referral_account": getattr(settings, 'JUPITER_REFERRAL_ACCOUNT', '')
        }
        
        # Store in Redis with 30-day expiry
        await redis_client.setex(
            f"fee:{tx_signature}", 
            2592000,  # 30 days
            json.dumps(fee_data)
        )
        
        # Also add to fee tracking list
        await redis_client.lpush("fee_tracking", json.dumps(fee_data))
        await redis_client.ltrim("fee_tracking", 0, 1000)  # Keep last 1000 fees
        
        # Convert fee to readable amount
        if "So111" in fee_mint:
            fee_readable = fee_amount / 1e9
            fee_unit = "SOL"
        elif "EPjFW" in fee_mint:
            fee_readable = fee_amount / 1e6
            fee_unit = "USDC"
        else:
            fee_readable = fee_amount
            fee_unit = "tokens"
        
        logger.info(f"💰 Fee recorded: {fee_readable:.6f} {fee_unit} from {wallet_address[:8]}...")
        
    except Exception as e:
        logger.error(f"Failed to store fee info: {e}")

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
        
        # Prepare explorer URLs BEFORE creating trade record
        explorer_urls = {}
        
        try:
            swap = await execute_jupiter_swap(
                user=user,
                input_mint=settings.SOL_MINT,
                output_mint=mint,
                amount=amount_lamports,
                slippage_bps=slippage_bps,
                label="BUY",
            )
            
            if swap.get("fee_applied"):
                await websocket_manager.send_personal_message(json.dumps({
                    "type": "log",
                    "message": f"💰 1% fee applied to this transaction",
                    "status": "info"
                }), user.wallet_address)
                
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
        
        # NOW, We define explorer_urls after we have the swap signature
        explorer_urls = {
            "solscan": f"https://solscan.io/tx/{swap['signature']}",
            "dexScreener": f"https://dexscreener.com/solana/{mint}",
            "jupiter": f"https://jup.ag/token/{mint}"
        }
        
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
            liquidity_at_buy=liquidity_usd,
            # Store buy URLs
            slippage_bps=slippage_bps,
            solscan_buy_url=explorer_urls["solscan"],
            dexscreener_url=explorer_urls["dexScreener"],
            jupiter_url=explorer_urls["jupiter"],
            # Set buy transaction hash
            buy_tx_hash=swap.get('signature'),
            # 🔥 FEE TRACKING - Fixed
            fee_applied=swap.get("fee_applied", False),
            fee_amount=float(swap.get("estimated_referral_fee", 0)) if swap.get("estimated_referral_fee") else None,
            fee_percentage=float(swap.get("fee_percentage", 0.0)) if swap.get("fee_percentage") else None,
            fee_bps=swap.get("fee_bps", None),
            fee_mint=swap.get("fee_mint", None),  # Fixed: Get from swap response
            fee_collected_at=datetime.utcnow() if swap.get("fee_applied") else None
        )
        db.add(trade)
        await db.commit()

        # Log successful save
        logger.info(f"Trade saved to database with ID: {trade.id}")
        
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
        
        # 🔥 Add fee notification
        if swap.get("fee_applied"):
            await websocket_manager.send_personal_message(json.dumps({
                "type": "log",
                "message": f"💰 1% fee applied to this buy transaction",
                "status": "info"
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
        
        # IMPORTANT: Re-raise the exception so the calling function knows it failed
        raise
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
#                 logger.debug(f"No price data for {mint[:8]}... - waiting")
#                 await asyncio.sleep(5)
#                 continue

#             price = float(dex["priceUsd"])
#             if entry_price_usd <= 0 or price <= 0:
#                 logger.debug(f"Invalid price for {mint[:8]}... - entry: ${entry_price_usd}, current: ${price}")
#                 await asyncio.sleep(5)
#                 continue
            
#             pnl = (price / entry_price_usd - 1) * 100
            
#             # Log PnL every 30 seconds for debugging
#             if int(datetime.utcnow().timestamp()) % 30 == 0:  # Every 30 seconds
#                 logger.info(f"Monitor {mint[:8]}...: ${price:.6f} | PnL: {pnl:.2f}% | TP: {user.sell_take_profit_pct}% | SL: {user.sell_stop_loss_pct}%")
#             else:
#                 logger.debug(f"Monitor {mint[:8]}...: ${price:.6f} | PnL: {pnl:.2f}%")

#             sell_reason = None
#             if user.sell_take_profit_pct and pnl >= user.sell_take_profit_pct:
#                 sell_reason = "TP"
#                 logger.info(f"TAKE PROFIT HIT for {mint[:8]}...: PnL {pnl:.2f}% >= {user.sell_take_profit_pct}%")
#             elif user.sell_stop_loss_pct and pnl <= -user.sell_stop_loss_pct:
#                 sell_reason = "SL"
#                 logger.info(f"STOP LOSS HIT for {mint[:8]}...: PnL {pnl:.2f}% <= -{user.sell_stop_loss_pct}%")
#             elif user.sell_timeout_seconds and (datetime.utcnow() - start).total_seconds() > user.sell_timeout_seconds:
#                 sell_reason = "Timeout"
#                 logger.info(f"TIMEOUT for {mint[:8]}...: {(datetime.utcnow() - start).total_seconds():.0f}s > {user.sell_timeout_seconds}s")

#             if sell_reason:
#                 logger.info(f"🚨 SELLING {mint[:8]}... - Reason: {sell_reason}, PnL: {pnl:.2f}%")
                
#                 # Send sell notification
#                 await websocket_manager.send_personal_message(json.dumps({
#                     "type": "log",
#                     "message": f"🚨 Selling {trade.token_symbol or mint[:8]} - {sell_reason} triggered (PnL: {pnl:.2f}%)",
#                     "status": "warning"
#                 }), user.wallet_address)
                
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
                
#                 # Prepare sell explorer URL
#                 sell_explorer_url = f"https://solscan.io/tx/{swap.get('signature')}"
                
#                 # Update trade record with sell URLs
#                 trade.sell_timestamp = datetime.utcnow()

#                 profit_usd = (price - entry_price_usd) * token_amount
#                 trade.sell_timestamp = datetime.utcnow()
#                 trade.profit_usd = round(profit_usd, 4)
#                 trade.sell_reason = sell_reason
#                 trade.price_usd_at_trade = price
#                 trade.sell_tx_hash = swap.get("signature") 
#                 trade.solscan_sell_url = sell_explorer_url
                
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
                
#                 # Send final sell confirmation
#                 await websocket_manager.send_personal_message(json.dumps({
#                     "type": "log",
#                     "message": f"✅ Sold {trade.token_symbol or mint[:8]}! Profit: ${profit_usd:.4f} ({pnl:.2f}%)",
#                     "status": "success"
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
                    
                try:
                    swap = await execute_jupiter_swap(
                        user=user,
                        input_mint=mint,
                        output_mint=settings.SOL_MINT,
                        amount=amount_lamports,
                        slippage_bps=slippage_bps,
                        label="SELL",
                    )
                except Exception as swap_error:
                    logger.error(f"SELL failed for {mint}: {swap_error}")
                    
                    # Send error message to user
                    await websocket_manager.send_personal_message(json.dumps({
                        "type": "log",
                        "message": f"❌ Sell failed: {str(swap_error)[:100]}",
                        "status": "error"
                    }), user.wallet_address)
                    break
                
                # Prepare sell explorer URL
                sell_explorer_url = f"https://solscan.io/tx/{swap.get('signature')}"
                
                # Update trade record with sell URLs
                trade.sell_timestamp = datetime.utcnow()
                profit_usd = (price - entry_price_usd) * token_amount
                trade.profit_usd = round(profit_usd, 4)
                trade.sell_reason = sell_reason
                trade.price_usd_at_trade = price
                trade.sell_tx_hash = swap.get("signature") 
                trade.solscan_sell_url = sell_explorer_url
                
                # 🔥 Store fee information if applied
                if swap.get("fee_applied"):
                    trade.fee_applied = True
                    trade.fee_amount = swap.get("estimated_referral_fee", 0)
                    trade.fee_percentage = swap.get("fee_percentage", 0.0)
                    
                    # Log fee collection
                    logger.info(f"💰 1% fee collected on SELL: {swap.get('estimated_referral_fee', 0)}")
                
                await db.commit()

                # 🔥 Enhanced trade instruction with fee info
                trade_instruction = {
                    "type": "trade_instruction",
                    "action": "sell",
                    "mint": mint,
                    "reason": sell_reason,
                    "pnl_pct": round(pnl, 2),
                    "profit_usd": round(profit_usd, 4),
                    "raw_tx_base64": swap["raw_tx_base64"],
                    "signature": swap["signature"],
                    "solscan_url": f"https://solscan.io/tx/{swap['signature']}"
                }
                
                # 🔥 Store fee information if applied
                if swap.get("fee_applied"):
                    trade.fee_applied = True
                    trade.fee_amount = swap.get("estimated_referral_fee", 0)
                    trade.fee_percentage = swap.get("fee_percentage", 0.0)
                    trade.fee_bps = swap.get("fee_bps", None)
                    trade.fee_mint = swap.get("fee_mint", None)  # Add this line
                    trade.fee_collected_at = datetime.utcnow()  # Add this line
                    
                    # Log fee collection
                    logger.info(f"💰 1% fee collected on SELL: {swap.get('estimated_referral_fee', 0)}")

                    
                    # Send fee notification
                    await websocket_manager.send_personal_message(json.dumps({
                        "type": "log",
                        "message": f"💰 1% fee applied to this sell transaction",
                        "status": "info"
                    }), user.wallet_address)
                else:
                    trade_instruction["fee_applied"] = False
                
                await websocket_manager.send_personal_message(json.dumps(trade_instruction), user.wallet_address)
                
                # Send final sell confirmation
                sell_message = f"✅ Sold {trade.token_symbol or mint[:8]}! Profit: ${profit_usd:.4f} ({pnl:.2f}%)"
                
                if swap.get("fee_applied"):
                    sell_message += f" (1% fee applied)"
                
                await websocket_manager.send_personal_message(json.dumps({
                    "type": "log",
                    "message": sell_message,
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
            
                    
            
            