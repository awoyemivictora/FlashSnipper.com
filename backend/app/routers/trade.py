import asyncio
from datetime import datetime
import json
from typing import Dict, List, Optional
from fastapi import HTTPException, Depends, Request, WebSocket, status, Query, APIRouter, BackgroundTasks
import httpx
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
import os
from dotenv import load_dotenv
import logging
from app.database import get_db
from app.dependencies import get_current_user_by_wallet
from app.middleware.rate_limiter import rate_limit, rate_limited
from app.models import Trade, User
from app.security import get_current_user
from app.schemas import GetTradeQuoteRequest, GetTradeQuoteResponse, LogTradeRequest, SendSignedTransactionRequest, SendSignedTransactionResponse
from app.utils.token_safety import check_token_safety
from app.utils.bot_logger import BotLogger, LogTemplates
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

router = APIRouter(prefix="/trade", tags=['Trade'])

# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_bots: Dict[str, UserTradingBot] = {}
        
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

# User Trading Bot Class
class UserTradingBot:
    def __init__(self, wallet_address: str, db: AsyncSession, user_settings: Dict):
        self.wallet_address = wallet_address
        self.db = db
        self.settings = user_settings
        self.is_running = False
        self.current_positions = {}
        self.bot_logger = BotLogger(wallet_address)
        self.last_balance_check = datetime.now()
        
    async def start(self):
        """Start the trading bot"""
        if self.is_running:
            return
            
        self.is_running = True
        await self.bot_logger.send_log(LogTemplates.bot_started(), "info")
        
        # Start background tasks
        asyncio.create_task(self._monitoring_loop())
        asyncio.create_task(self._balance_check_loop())
        
    async def stop(self):
        """Stop the trading bot"""
        self.is_running = False
        await self.bot_logger.send_log("Bot stopped successfully", "info")
        
    async def update_settings(self, new_settings: Dict):
        """Update bot settings in real-time"""
        self.settings.update(new_settings)
        await self.bot_logger.send_log("Bot settings updated successfully", "info")
        
    async def _monitoring_loop(self):
        """Main monitoring loop for new pools and trading opportunities"""
        while self.is_running:
            try:
                # Check for new pools on selected DEXes
                await self._check_new_pools()
                
                # Monitor existing positions for sell conditions
                await self._monitor_positions()
                
                await asyncio.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                logger.error(f"Monitoring error for {self.wallet_address}: {e}")
                await asyncio.sleep(5)
                
    async def _check_new_pools(self):
        """Check for new pools on configured DEXes"""
        # This would integrate with your existing pool detection logic
        # For now, we'll simulate pool detection
        try:
            # Your existing pool detection logic here
            # Example: detect new Raydium pools
            detected_pools = await self._detect_raydium_pools()
            
            for pool in detected_pools:
                await self.bot_logger.send_log(
                    LogTemplates.new_pool_detected("Raydium", pool.get('symbol', 'Unknown')),
                    "info",
                    token_symbol=pool.get('symbol')
                )
                
                # Check if pool meets user criteria
                if await self._meets_trading_criteria(pool):
                    await self.bot_logger.send_log(
                        LogTemplates.waiting_for_conditions(),
                        "info",
                        token_symbol=pool.get('symbol')
                    )
                    
                    # Execute buy if conditions are met
                    if await self._should_execute_buy(pool):
                        await self._execute_buy_order(pool)
                        
        except Exception as e:
            logger.error(f"Pool check error: {e}")
            
    async def _detect_raydium_pools(self) -> List[Dict]:
        """Detect new Raydium pools - integrate with your existing logic"""
        # This should integrate with your raydium_apis.py
        return []  # Return list of detected pools
    
    async def _meets_trading_criteria(self, pool: Dict) -> bool:
        """Check if pool meets user's trading criteria"""
        try:
            # Implement your safety checks and user criteria
            safety_report = await check_token_safety(pool['mint_address'])
            
            # Check user-specific filters
            if self.settings.get('filter_top_holders_max_pct'):
                if safety_report.get('top_holders_percentage', 100) > self.settings['filter_top_holders_max_pct']:
                    return False
                    
            # Add more criteria checks based on user settings
            return safety_report.get('passed_all_checks', False)
            
        except Exception as e:
            logger.error(f"Criteria check error: {e}")
            return False
            
    async def _should_execute_buy(self, pool: Dict) -> bool:
        """Determine if we should execute a buy based on market conditions"""
        # Implement your buy logic here
        return True
        
    async def _execute_buy_order(self, pool: Dict):
        """Execute a buy order for the detected pool"""
        try:
            await self.bot_logger.send_log(
                LogTemplates.attempting_buy(pool.get('symbol', 'Unknown')),
                "info",
                token_symbol=pool.get('symbol')
            )
            
            # Your existing buy execution logic
            buy_result = await self._execute_trade(
                mint_address=pool['mint_address'],
                amount=self.settings.get('buy_amount_sol', 0.1),
                trade_type="buy"
            )
            
            if buy_result and buy_result.get('success'):
                # Add to positions
                self.current_positions[pool['mint_address']] = {
                    'buy_price': buy_result['price'],
                    'amount': buy_result['amount'],
                    'token_symbol': pool.get('symbol'),
                    'buy_time': datetime.now()
                }
                
        except Exception as e:
            logger.error(f"Buy execution error: {e}")
            await self.bot_logger.send_log(f"Buy execution failed: {str(e)}", "error")
            
    async def _monitor_positions(self):
        """Monitor existing positions for sell conditions"""
        for mint_address, position in list(self.current_positions.items()):
            try:
                current_price = await self._get_current_price(mint_address)
                buy_price = position['buy_price']
                
                # Check take profit
                take_profit_pct = self.settings.get('sell_take_profit_pct', 50)
                if current_price >= buy_price * (1 + take_profit_pct / 100):
                    await self._execute_sell_order(mint_address, position, "take_profit")
                    continue
                    
                # Check stop loss
                stop_loss_pct = self.settings.get('sell_stop_loss_pct', 20)
                if current_price <= buy_price * (1 - stop_loss_pct / 100):
                    await self._execute_sell_order(mint_address, position, "stop_loss")
                    continue
                    
            except Exception as e:
                logger.error(f"Position monitoring error: {e}")
                
    async def _execute_sell_order(self, mint_address: str, position: Dict, reason: str):
        """Execute a sell order"""
        try:
            await self.bot_logger.send_log(
                LogTemplates.send_sell_attempt(),
                "info",
                token_symbol=position.get('token_symbol')
            )
            
            sell_result = await self._execute_trade(
                mint_address=mint_address,
                amount=position['amount'],
                trade_type="sell"
            )
            
            if sell_result and sell_result.get('success'):
                await self.bot_logger.send_log(
                    LogTemplates.transaction_executed(),
                    "info",
                    token_symbol=position.get('token_symbol')
                )
                
                # Wait for confirmation
                if await self._confirm_transaction(sell_result['tx_hash']):
                    await self.bot_logger.send_log(
                        LogTemplates.transaction_confirmed(),
                        "info",
                        token_symbol=position.get('token_symbol')
                    )
                    
                    await self.bot_logger.send_log(
                        LogTemplates.sell_confirmed(sell_result['tx_hash']),
                        "success",
                        tx_hash=sell_result['tx_hash'],
                        token_symbol=position.get('token_symbol')
                    )
                    
                    # Remove from positions
                    self.current_positions.pop(mint_address, None)
                    
        except Exception as e:
            logger.error(f"Sell execution error: {e}")
            await self.bot_logger.send_log(f"Sell execution failed: {str(e)}", "error")
            
    async def _execute_trade(self, mint_address: str, amount: float, trade_type: str) -> Optional[Dict]:
        """Execute a trade using your existing logic"""
        # Integrate with your existing trade execution logic
        try:
            # Your existing trade execution code here
            return {"success": True, "tx_hash": "simulated_tx_hash", "price": 0.001}
        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            return None
            
    async def _get_current_price(self, mint_address: str) -> float:
        """Get current token price"""
        # Implement price fetching logic
        return 0.001
        
    async def _confirm_transaction(self, tx_hash: str) -> bool:
        """Confirm transaction on blockchain"""
        # Implement transaction confirmation logic
        return True
        
    async def _balance_check_loop(self):
        """Periodically check SOL balance and stop bot if insufficient"""
        while self.is_running:
            try:
                if await self._get_sol_balance() < 0.1:  # Minimum SOL threshold
                    await self.bot_logger.send_log(
                        "Bot stopping automatically - insufficient SOL balance",
                        "warning"
                    )
                    await self.stop()
                    break
                    
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Balance check error: {e}")
                await asyncio.sleep(60)
                
    async def _get_sol_balance(self) -> float:
        """Get current SOL balance"""
        # Implement balance checking logic
        return 1.0  # Simulated balance



# User Trade Endpoints
@router.post("/bot/start")
async def start_bot(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Start the trading bot for authenticated user"""
    if current_user.wallet_address in websocket_manager.user_bots:
        raise HTTPException(status_code=400, detail="Bot is already running")
        
    # Convert user settings to dict
    user_settings = {
        'buy_amount_sol': current_user.buy_amount_sol or 0.1,
        'sell_take_profit_pct': current_user.sell_take_profit_pct or 50,
        'sell_stop_loss_pct': current_user.sell_stop_loss_pct or 20,
        # Add all other user settings...
    }
    
    # Create and start bot
    bot = UserTradingBot(current_user.wallet_address, db, user_settings)
    websocket_manager.user_bots[current_user.wallet_address] = bot
    
    background_tasks.add_task(bot.start)
    
    return {"status": "Bot started successfully"}

@router.post("/bot/stop")
async def stop_bot(current_user: User = Depends(get_current_user)):
    """Stop the trading bot for authenticated user"""
    if current_user.wallet_address not in websocket_manager.user_bots:
        raise HTTPException(status_code=400, detail="Bot is not running")
        
    bot = websocket_manager.user_bots[current_user.wallet_address]
    await bot.stop()
    del websocket_manager.user_bots[current_user.wallet_address]
    
    return {"status": "Bot stopped successfully"}

@router.get("/bot/status")
async def get_bot_status(current_user: User = Depends(get_current_user)):
    """Get current bot status"""
    is_running = current_user.wallet_address in websocket_manager.user_bots
    return {"is_running": is_running}

@router.websocket("/ws/{wallet_address}")
async def websocket_endpoint(websocket: WebSocket, wallet_address: str, db: AsyncSession = Depends(get_db)):
    await websocket_manager.connect(websocket, wallet_address)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket_manager.send_personal_message(
                    json.dumps({"type": "pong", "timestamp": datetime.now().isoformat()}),
                    wallet_address
                )
                
    except Exception as e:
        logger.error(f"WebSocket error for {wallet_address}: {e}")
    finally:
        websocket_manager.disconnect(wallet_address)

@router.post("/quote", response_model=GetTradeQuoteResponse)
async def get_trade_quote(request: GetTradeQuoteRequest):
    """
    Fetches a trade quote and an unsigned transaction from a DEX aggregator.
    The frontend will then sign this transaction.
    """
    logger.info(f"Fetching quote for {request.trade_type} {request.in_amount} {request.token_in_address} to {request.token_out_address}")

    # Your old trader.js logic for fetching the quote:
    # `const quoteUrl = `${API_HOST}/defi/router/v1/sol/tx/get_swap_route?token_in_address=${inputToken}&token_out_address=${mint_address}&in_amount=${amount}&from_address=${fromAddress}&slippage=${slippage}&fee=${fee}`;`

    # Dynamically build the URL based on request.trade_type (buy/sell)
    # Assuming 'token_in_address' and 'token_out_address' define the swap direction.
    # For a 'buy', token_in_address would be SOL, token_out_address would be the token to buy.
    # For a 'sell', token_in_address would be the token to sell, token_out_address would be SOL.

    # Example for Pumpportal's API or a similar aggregator
    # You'll need to adapt this to the actual API you're using (e.g., your DEX_AGGREGATOR_API_HOST)
    # The `amount` in their API often means the "in_amount" in lamports if SOL, or smallest units if token.
    # So `request.in_amount` (float SOL) needs conversion if `token_in_address` is SOL.

    # Example using a hypothetical generic DEX aggregator API structure:
    try:
        async with httpx.AsyncClient() as client:
            # Adjust 'in_amount' for lamports if it's SOL
            if request.token_in_address == "So11111111111111111111111111111111111111112": # Solana's mint address
                in_amount_lamports = int(request.in_amount * 1_000_000_000)
            else:
                # If the input token is not SOL, `in_amount` should be in its smallest units
                # You might need to fetch token decimals here or pass them from frontend
                # For now, let's assume frontend sends smallest units if not SOL
                in_amount_lamports = int(request.in_amount) # This needs careful handling for decimals

            # This `get_swap_route` URL structure is from your old trader.js
            quote_params = {
                "token_in_address": request.token_in_address,
                "token_out_address": request.token_out_address,
                "in_amount": in_amount_lamports, # Ensure this is in smallest units
                "from_address": request.user_wallet_address,
                "slippage": request.slippage,
            }
            if request.fee is not None:
                quote_params["fee"] = request.fee

            quote_url = f"{settings.DEX_AGGREGATOR_API_HOST}/defi/router/v1/sol/tx/get_swap_route"
            response = await client.get(quote_url, params=quote_params)
            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            quote_data = response.json()

            # Validate response structure (adjust based on your actual aggregator's response)
            if not quote_data or not quote_data.get('data', {}).get('raw_tx', {}).get('swapTransaction'):
                raise HTTPException(status_code=400, detail="Invalid quote response from aggregator.")

            unsigned_tx_base64 = quote_data['data']['raw_tx']['swapTransaction']
            last_valid_block_height = quote_data['data']['raw_tx']['lastValidBlockHeight']

            # Return the unsigned transaction and blockhash for frontend to sign
            return GetTradeQuoteResponse(
                raw_tx_base64=unsigned_tx_base64,
                last_valid_block_height=last_valid_block_height,
                quote_data=quote_data['data']['quote'] # Pass relevant quote details back
            )

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching quote: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"DEX aggregator error: {e.response.text}")
    except httpx.RequestError as e:
        logger.error(f"Network error fetching quote: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not connect to DEX aggregator.")
    except Exception as e:
        logger.error(f"Error fetching trade quote: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get trade quote: {e}")

@router.post("/execute")
async def execute_trade_with_checks(
    mint_address: str = Query(..., description="Token mint address to trade"),
    amount: float = Query(..., description="Amount to trade in SOL"),
    trade_type: str = Query(..., regex="^(buy|sell)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes a trade with safety checks and applies 1% fee for free users
    """
    # 1. Perform safety checks (for buys only)
    if trade_type == "buy":
        safety_report = await check_token_safety(mint_address)
        if not safety_report["passed_all_checks"]:
            raise HTTPException(status_code=400, detail=f"Token failed safery check: {safety_report}")
        
    # 2. Calculate amount after fee (1% for free users)
    fee_percent = 0.01 if not current_user.is_premium else 0
    fee_amount = amount * fee_percent
    trade_amount = amount - fee_amount
    
    # 3. Get trade quote (from the existing function)
    quote_request = GetTradeQuoteRequest(
        trade_type=trade_type,
        token_in_address="So11111111111111111111111111111111111111112" if trade_type == "buy" else mint_address,
        token_out_address=mint_address if trade_type == "buy" else "So11111111111111111111111111111111111111112",
        in_amount=trade_amount,
        user_wallet_address=current_user.wallet_address,
        slippage=5  # COMING BACK TO THIS (since the slippage has to be manually set by each user from the frontend)
    )
    
    quote_response = await get_trade_quote(quote_request)
    
    # 4. Return unsigned tranasction to frontend
    return {
        "unsigned_tx": quote_response.raw_tx_base64,
        "last_valid_block_height": quote_response.last_valid_block_height,
        "fee_amount": fee_amount,
        "trade_amount": trade_amount,
        "safety_report": safety_report if trade_type == "buy" else None
    }
    
@router.post("/send-signed-transaction", response_model=SendSignedTransactionResponse)
async def send_signed_transaction(request: SendSignedTransactionRequest):
    """
    Receives a Base64 encoded signed transaction from the frontend and broadcasts it to Solana.
    """
    logger.info(f"Received signed transaction for broadcast.")
    try:
        # Your old trader.js logic for submitting transaction:
        # const submitUrl = `${API_HOST}/txproxy/v1/send_transaction`;
        # let res = await fetch(submitUrl, { method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({"chain": "sol", "signedTx": signedTx})});

        async with httpx.AsyncClient() as client:
            submit_url = f"{settings.DEX_AGGREGATOR_API_HOST}/txproxy/v1/send_transaction"
            response = await client.post(
                submit_url,
                json={
                    "chain": request.chain,
                    "signedTx": request.signed_tx_base64
                }
            )
            response.raise_for_status()
            result = response.json()

            if not result.get('data', {}).get('hash'):
                raise HTTPException(status_code=400, detail=result.get('msg', 'Unknown error broadcasting transaction.'))

            transaction_hash = result['data']['hash']
            logger.info(f"Transaction broadcasted. Hash: {transaction_hash}")
            return SendSignedTransactionResponse(transaction_hash=transaction_hash)

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error broadcasting transaction: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Transaction broadcast error: {e.response.text}")
    except httpx.RequestError as e:
        logger.error(f"Network error broadcasting transaction: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not connect to transaction broadcast service.")
    except Exception as e:
        logger.error(f"Error sending signed transaction: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to send transaction: {e}")

# @router.post("/log-trade")
# async def log_trade(request: LogTradeRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
#     """
#     Receives trade details from the frontend to log in the backend database.
#     This replaces the database updates in your old trader.js.
#     """
#     if current_user.wallet_address != request.user_wallet_address:
#         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not authorized to log trade for this wallet.")

#     logger.info(f"Logging {request.trade_type} trade for {request.user_wallet_address} on {request.mint_address}")

#     try:
#         # Decide which table to update based on trade_type, or use a single `Trade` table
#         # Your `Trade` model in `app/models.py` should be able to store all this.
#         trade_record = Trade(
#             user_wallet_address=request.user_wallet_address,
#             mint_address=request.mint_address,
#             token_symbol=request.token_symbol,
#             trade_type=request.trade_type,
#             amount_sol=request.amount_sol,
#             amount_tokens=request.amount_tokens,
#             price_sol_per_token=request.price_sol_per_token,
#             price_usd_at_trade=request.price_usd_at_trade,
#             tx_hash=request.tx_hash,
#             log_message=request.log_message,
#             profit_usd=request.profit_usd,
#             profit_sol=request.profit_sol,
#             # Add new fields for buy/sell
#             buy_price=request.buy_price,
#             entry_price=request.entry_price,
#             stop_loss=request.stop_loss,
#             take_profit=request.take_profit,
#             token_amounts_purchased=request.token_amounts_purchased,
#             token_decimals=request.token_decimals,
#             sell_reason=request.sell_reason,
#             swap_provider=request.swap_provider
#         )
#         db.add(trade_record)
#         await db.commit()
#         await db.refresh(trade_record)

#         # You might also update `TokenMetadata` here if you had `is_bought`, `is_sold` flags
#         # related to specific tokens in your database.
#         # This part depends on how you want to manage token metadata vs. trade history.
#         # Example for `TokenMetadata` update (requires `TokenMetadata` model and logic):
#         # if request.trade_type == "buy":
#         #    # Update TokenMetadata for 'is_bought' etc.
#         #    metadata = await db.execute(select(TokenMetadata).filter_by(mint_address=request.mint_address)).scalar_one_or_none()
#         #    if metadata:
#         #        metadata.is_bought = True
#         #        metadata.buy_timestamp = datetime.now()
#         #        metadata.buy_price = request.buy_price
#         #        # ... other fields
#         # else: # sell
#         #    # Update TokenMetadata for 'is_sold' etc.
#         #    metadata = await db.execute(select(TokenMetadata).filter_by(mint_address=request.mint_address)).scalar_one_or_none()
#         #    if metadata:
#         #        metadata.is_sold = True
#         #        metadata.sell_timestamp = datetime.now()
#         #        # ... other fields
#         # await db.commit() # Commit metadata changes if done here

#         await websocket_manager.send_personal_message(
#             json.dumps({"type": "trade_log", "data": trade_record.dict()}), # Send full trade record
#             request.user_wallet_address
#         )
#         return {"status": "Trade logged successfully"}
#     except Exception as e:
#         logger.error(f"Error logging trade for {request.user_wallet_address}: {e}", exc_info=True)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to log trade: {e}")

@router.get("/profit-per-trade")
async def get_total_profit(
    current_user: User = Depends(get_current_user_by_wallet),
    db: AsyncSession = Depends(get_db),
    _: bool = rate_limited(calls=5, per_seconds=60)  # FIXED
):
    try:
        # Fetch all trades for the user
        result = await db.execute(
            select(Trade).filter_by(user_wallet_address=current_user.wallet_address)
        )
        trades = result.scalars().all()
        
        total_profit = 0.0
        for trade in trades:
            # Assume Trade model has amount_sol_in (buy) and amount_sol_out (sell)
            # Profit = amount_sol_out - amount_sol_in for completed trades
            if trade.trade_type == "completed" and trade.amount_sol_in and trade.amount_sol_out:
                profit = trade.amount_sol_out - trade.amount_sol_in
                total_profit += profit
        
        logger.info(f"Retrieved total profit for {current_user.wallet_address}: {total_profit} SOL")
        return {"total_profit": total_profit}
    except Exception as e:
        logger.error(f"Failed to retrieve total profit for {current_user.wallet_address}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve total profit")
    
@router.get("/lifetime-profit")
async def get_total_profit(
    current_user: User = Depends(get_current_user_by_wallet),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Trade).where(Trade.user_wallet_address == current_user.wallet_address)
    )
    trades = result.scalars().all()

    total_profit = sum(t.profit_sol or 0 for t in trades if t.profit_sol)

    return {
        "total_profit": round(total_profit, 4),
        "is_positive": total_profit >= 0
    }

@router.get("/sniped-count")
async def get_sniped_count(
    current_user: User = Depends(get_current_user_by_wallet),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Trade)
        .where(Trade.user_wallet_address == current_user.wallet_address)
        .where(Trade.trade_type == "buy")
    )
    count = len(result.scalars().all())
    return {"sniped_count": count}

@router.get("/history")
async def get_trade_history(
    current_user: User = Depends(get_current_user_by_wallet),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Trade)
        .where(Trade.user_wallet_address == current_user.wallet_address)
        .order_by(Trade.buy_timestamp.desc(), Trade.sell_timestamp.desc())
    )
    trades = result.scalars().all()

    history = []
    for trade in trades:
        if trade.trade_type == "buy":
            history.append({
                "id": trade.id,
                "type": "buy",
                "token": trade.token_symbol or "UNKNOWN",
                "amount_sol": trade.amount_sol,
                "amount_tokens": trade.token_amounts_purchased,
                "tx_hash": trade.buy_tx_hash,
                "timestamp": trade.buy_timestamp or datetime.utcnow(),
                "token_logo": f"https://dd.dexscreener.com/ds-logo/solana/{trade.mint_address}.png"
            })
        if trade.trade_type == "sell" or trade.profit_sol is not None:
            history.append({
                "id": trade.id,
                "type": "sell",
                "token": trade.token_symbol or "UNKNOWN",
                "amount_sol": abs(trade.profit_sol or 0) + (trade.amount_sol or 0),
                "amount_tokens": trade.token_amounts_purchased,
                "tx_hash": trade.sell_tx_hash or trade.buy_tx_hash,
                "timestamp": trade.sell_timestamp or trade.buy_timestamp,
                "profit_sol": trade.profit_sol,
                "token_logo": f"https://dd.dexscreener.com/ds-logo/solana/{trade.mint_address}.png"
            })

    return history
    
    