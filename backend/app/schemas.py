from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime



class WalletRegisterRequest(BaseModel):
    wallet_address: str
    encrypted_private_key: str  # This will be the XOR-encrypted string from frontend

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    wallet_address: str # Add wallet_address to response for client convenience
    

class UserProfile(BaseModel):
    wallet_address: str
    is_active: bool
    is_premium: bool
    
    
class SnipeLog(BaseModel):
    id: str
    user_wallet_address: str
    mint_address: str
    started_at: datetime
    
    class Config:
        from_attributes = True  # For SQLAlchemy ORM models
        
        
class TradeLog(BaseModel):
    id: str
    user_wallet_address: str
    mint_address: str
    token_symbol: Optional[str]
    trade_type: str
    amount_sol: Optional[float]
    amount_tokens: Optional[float]
    price_sol_per_token: Optional[float]
    price_usd_at_trade: Optional[float]
    tx_hash: Optional[str]
    timestamp: datetime
    profit_usd: Optional[float]
    profit_sol: Optional[float]
    log_message: Optional[str]
    
    class Config:
        from_attributes = True
        





class BotSettingsUpdate(BaseModel):
    buy_amount_sol: Optional[float] = None
    buy_priority_fee_lamports: Optional[int] = None
    buy_slippage_bps: Optional[int] = None
    sell_take_profit_pct: Optional[float] = None
    sell_stop_loss_pct: Optional[float] = None
    sell_timeout_seconds: Optional[int] = None
    sell_priority_fee_lamports: Optional[int] = None
    sell_slippage_bps: Optional[int] = None
    enable_trailing_stop_loss: Optional[bool] = None
    trailing_stop_loss_pct: Optional[float] = None




class GetTradeQuoteRequest(BaseModel):
    token_in_address: str
    token_out_address: str
    in_amount: float    # Amount in SOL (float)
    user_wallet_address: str
    slippage: float = 0.005 # Default 0.5%
    fee: Optional[float] = None # Fee for the platform if any
    

class GetTradeQuoteResponse(BaseModel):
    raw_tx_base64: str  # Base64 encoded unsigned transaction from the DEX aggregator
    last_valid_block_height: int
    quote_data: dict    # Any relevant quote details to pass back (e.g., outAmount, priceImpact)
    
    
class SendSignedTransactionRequest(BaseModel):
    signed_tx_base64: str   # Base64 encoded signed transaction from the frontend
    chain: str = "sol"  # Chain name, always "sol" for Solana
    
    
class SendSignedTransactionResponse(BaseModel):
    transaction_hash: str
    
    
class LogTradeRequest(BaseModel):
    mint_address: str
    token_symbol: str
    trade_type: str # "buy" or "sell"
    amount_sol: float
    amount_tokens: float
    price_sol_per_token: float
    price_usd_at_trade: float
    tx_hash: str
    log_message: str
    profit_usd: Optional[float] = None
    profit_sol: Optional[float] = None
    buy_price: Optional[float] = None   # For buy trades
    entry_price: Optional[float] = None # For buy trades
    stop_loss: Optional[float] = None   # For buy trades
    take_profit: Optional[float] = None # For buy trades
    token_amounts_purchased: Optional[float] = None     # For buy trades
    token_decimals: Optional[int] = None    # For buy trades
    sell_reason: Optional[str] = None   # For sell trades
    swap_provider: Optional[str] = None # For sell trades





class AIAnalysisRequest(BaseModel):
    token_address: str = Field(..., min_length=32, max_length=44, description="Solana token mint address")
    
    
class AIAnalysisResponse(BaseModel):
    token_address: str
    sentiment_score: Optional[float] = None
    openai_analysis_summary: Optional[str] = None
    rug_check_result: Optional[str] = None
    rug_check_details: Optional[Dict[str, Any]] = None
    
    # Premium features
    top_10_holders_percentage: Optional[float] = None
    lp_locked: Optional[bool] = None
    mint_authority_revoked: Optional[bool] = None
    
    analyzed_at: datetime
    
    
    class Config:
        from_attributes = True



class SnipeBase(BaseModel):
    token_address: str = Field(..., min_length=32, max_length=44, description="Solana token mint address")
    amount_sol: float = Field(..., gt=0, description="Amount of SOL to use for the snipe")
    slippage: float = Field(0.01, ge=0, le=0.5, description="Slippage tolerance (e.g., 0.01 for 1%)")
    is_buy: bool = Field(..., description="True for buy, False for sell")
    
    
class SnipeCreate(SnipeBase):
    pass


class SnipeUpdate(BaseModel):
    status: Optional[str] = None
    transaction_signature: Optional[str] = None
    profit_loss: Optional[float] = None 
    logs: Optional[List[Any]] = None    # Use Any for dynamic log entries
    
    
class SnipeResponse(SnipeBase):
    id: str
    user_wallet_address: str
    status: str
    transaction_signature: Optional[str] = None
    profit_loss: Optional[float] = None
    started_at: datetime 
    completed_at: Optional[datetime] = None
    logs: List[Any] = []
    
    
    class Config:
        from_attributes = True
    
    
    

class SubscriptionRequest(BaseModel):
    email: EmailStr # Required for linking subscription to a user
    
    

class SubscriptionResponse(BaseModel):
    id: str
    user_wallet_address: str
    plan_name: str
    is_active: bool
    start_date: datetime
    end_date: Optional[datetime] = None
    
    
    class Config:
        from_attributes = True



class UserBase(BaseModel):
    wallet_address: str
    email: Optional[EmailStr] = None
    
    
class UserCreate(UserBase):
    # For automatic wallet generation, the backend generates these
    # We might not need this for direct user creation if wallet is auto-generated
    pass


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    is_premium: Optional[bool] = None
    

class UserResponse(UserBase):
    is_premium: bool 
    created_at: datetime 
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True  # Changed from orm_mode = True in Pydantic v2
        
        
        

class WalletResponse(BaseModel):
    wallet_address: str
    private_key: str
    sol_balance: float
    
    
    
    
 
        
# --- NEW SCHEMAS FOR BOT SETTINGS ---

class UserBotSettingsBase(BaseModel):
    """Base schema for bot settings, containing common fields."""
    buy_amount_sol: float = Field(..., description="Amount of SOL to use for buying tokens.")
    buy_priority_fee_lamports: int = Field(..., description="Priority fee in lamports for buy transactions.")
    buy_slippage_bps: int = Field(..., description="Slippage in basis points (e.g., 500 for 5%) for buy transactions.")

    sell_take_profit_pct: float = Field(..., description="Take profit percentage for selling.")
    sell_stop_loss_pct: float = Field(..., description="Stop loss percentage for selling.")
    sell_timeout_seconds: int = Field(..., description="Timeout in seconds for selling attempts.")
    sell_priority_fee_lamports: int = Field(..., description="Priority fee in lamports for sell transactions.")
    sell_slippage_bps: int = Field(..., description="Slippage in basis points (e.g., 500 for 5%) for sell transactions.")
    enable_trailing_stop_loss: bool = Field(..., description="Enable trailing stop loss.")
    trailing_stop_loss_pct: Optional[float] = Field(None, description="Trailing stop loss percentage.")

    # Basic Filters
    filter_socials_added: bool = Field(..., description="Filter for tokens with linked social media.")
    filter_liquidity_burnt: bool = Field(..., description="Filter for tokens with burnt liquidity.")
    filter_immutable_metadata: bool = Field(..., description="Filter for tokens with immutable metadata.")
    filter_mint_authority_renounced: bool = Field(..., description="Filter for tokens with renounced mint authority.")
    filter_freeze_authority_revoked: bool = Field(..., description="Filter for tokens with revoked freeze authority.")
    filter_pump_fun_migrated: bool = Field(..., description="Filter for tokens migrated from Pump.fun.")
    filter_check_pool_size_min_sol: float = Field(..., description="Minimum liquidity pool size in SOL.")

    # Bot operation settings
    bot_check_interval_seconds: int = Field(..., description="Interval in seconds for the bot to check for new tokens.")
    
    # Premium status (read-only from frontend's perspective for this endpoint)
    is_premium: bool = Field(..., description="Whether the user has premium access.")


class UserBotSettingsResponse(UserBotSettingsBase):
    """Response schema for fetching user bot settings."""
    # Add any other fields you want to explicitly return, e.g.,
    # custom_rpc_https: Optional[str] = None
    # custom_rpc_wss: Optional[str] = None

    class Config:
        from_attributes = True # Was orm_mode = True in Pydantic v1.x


class UserBotSettingsUpdate(UserBotSettingsBase):
    """Request schema for updating user bot settings."""
    # For PUT, we expect all fields. If using PATCH, make all fields Optional here
    # For PUT, the client sends the entire object.
    # For PATCH, the client sends only the fields they want to change.
    # Given your frontend sends `botSettings` as a whole, PUT is suitable.
    pass





