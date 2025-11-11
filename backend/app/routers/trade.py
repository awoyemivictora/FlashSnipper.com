import json
from typing import Dict
from fastapi import HTTPException, Depends, WebSocket, status, Query, APIRouter
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
import os
from dotenv import load_dotenv
import logging
from app.database import get_db
from app.models import Trade, User
from app.security import get_current_user
from app.schemas import GetTradeQuoteRequest, GetTradeQuoteResponse, LogTradeRequest, SendSignedTransactionRequest, SendSignedTransactionResponse
from app.utils.token_safety import check_token_safety

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

router = APIRouter(
    prefix="/trade",
    tags=['Trade']
)




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
        for connection in self.active_connections.values():
            await connection.send_text(message)
            

websocket_manager = ConnectionManager()


# ---- Get Trade Quote (for frontend to build transactions) ------
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

            quote_url = f"{DEX_AGGREGATOR_API_HOST}/defi/router/v1/sol/tx/get_swap_route"
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
    





# --- New Endpoint: Send Signed Transaction (from Frontend) ---
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
            submit_url = f"{DEX_AGGREGATOR_API_HOST}/txproxy/v1/send_transaction"
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



# --- Endpoint to Log Trade History (from Frontend) ---
@router.post("/log-trade")
async def log_trade(request: LogTradeRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Receives trade details from the frontend to log in the backend database.
    This replaces the database updates in your old trader.js.
    """
    if current_user.wallet_address != request.user_wallet_address:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not authorized to log trade for this wallet.")

    logger.info(f"Logging {request.trade_type} trade for {request.user_wallet_address} on {request.mint_address}")

    try:
        # Decide which table to update based on trade_type, or use a single `Trade` table
        # Your `Trade` model in `app/models.py` should be able to store all this.
        trade_record = Trade(
            user_wallet_address=request.user_wallet_address,
            mint_address=request.mint_address,
            token_symbol=request.token_symbol,
            trade_type=request.trade_type,
            amount_sol=request.amount_sol,
            amount_tokens=request.amount_tokens,
            price_sol_per_token=request.price_sol_per_token,
            price_usd_at_trade=request.price_usd_at_trade,
            tx_hash=request.tx_hash,
            log_message=request.log_message,
            profit_usd=request.profit_usd,
            profit_sol=request.profit_sol,
            # Add new fields for buy/sell
            buy_price=request.buy_price,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            token_amounts_purchased=request.token_amounts_purchased,
            token_decimals=request.token_decimals,
            sell_reason=request.sell_reason,
            swap_provider=request.swap_provider
        )
        db.add(trade_record)
        await db.commit()
        await db.refresh(trade_record)

        # You might also update `TokenMetadata` here if you had `is_bought`, `is_sold` flags
        # related to specific tokens in your database.
        # This part depends on how you want to manage token metadata vs. trade history.
        # Example for `TokenMetadata` update (requires `TokenMetadata` model and logic):
        # if request.trade_type == "buy":
        #    # Update TokenMetadata for 'is_bought' etc.
        #    metadata = await db.execute(select(TokenMetadata).filter_by(mint_address=request.mint_address)).scalar_one_or_none()
        #    if metadata:
        #        metadata.is_bought = True
        #        metadata.buy_timestamp = datetime.now()
        #        metadata.buy_price = request.buy_price
        #        # ... other fields
        # else: # sell
        #    # Update TokenMetadata for 'is_sold' etc.
        #    metadata = await db.execute(select(TokenMetadata).filter_by(mint_address=request.mint_address)).scalar_one_or_none()
        #    if metadata:
        #        metadata.is_sold = True
        #        metadata.sell_timestamp = datetime.now()
        #        # ... other fields
        # await db.commit() # Commit metadata changes if done here

        await websocket_manager.send_personal_message(
            json.dumps({"type": "trade_log", "data": trade_record.dict()}), # Send full trade record
            request.user_wallet_address
        )
        return {"status": "Trade logged successfully"}
    except Exception as e:
        logger.error(f"Error logging trade for {request.user_wallet_address}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to log trade: {e}")



