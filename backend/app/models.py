from datetime import datetime
from typing import Any, Dict, List
from typing import Optional
import uuid
from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship


class Base(DeclarativeBase):
    pass


# This table saves new pumpfun tokens gotten from pumpportal
class NewTokens(Base):
    __tablename__ = "new_tokens"

    mint_address: Mapped[str] = mapped_column(String, primary_key=True, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    # price_in_usd: Mapped[float] = mapped_column(Float, nullable=False)
    # volume: Mapped[float] = mapped_column(Float, nullable=False)
    # liquidity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    # New columns from Pumpportal events:
    signature: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    trader_public_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tx_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    initial_buy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sol_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bonding_curve_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    v_tokens_in_bonding_curve: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    v_sol_in_bonding_curve: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    market_cap_sol: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    uri: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pool: Mapped[Optional[str]] = mapped_column(String, nullable=True)



class TokenMetadata(Base):
    __tablename__ = "token_metadata"

    mint_address: Mapped[str] = mapped_column(String, primary_key=True, nullable=False, unique=True)

    # Basic token and pair info
    dexscreener_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pair_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    dex_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    price_native: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    price_usd: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    liquidity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    market_cap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pair_created_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # epoch timestamp

    # Base token details
    token_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    token_symbol: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Volume data
    volume_h24: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_h6: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_h1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_m5: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Price change data
    price_change_h24: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_change_h6: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_change_h1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_change_m5: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Token website and socials
    websites: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    twitter: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    telegram: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # New field to store the entry price of a trade.
    entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Fields for candidate analysis
    is_candidate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_notified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Fields for token details
    token_decimals: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_amounts_purchased: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sol_amounts_received: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Fields for tracking live trades
    is_bought: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_sold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    buy_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sell_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    buy_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sell_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sell_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    profit_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    profit_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # New field for transaction hash
    buy_tx_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sell_tx_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    swap_provider: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    last_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # === Basic Filters coming from Solscan and Raydium API===
    socials_present: Mapped[bool] = mapped_column(Boolean, default=False)
    liquidity_burnt: Mapped[bool] = mapped_column(Boolean, default=False)
    immutable_metadata: Mapped[bool] = mapped_column(Boolean, default=False)
    mint_authority_renounced: Mapped[bool] = mapped_column(Boolean, default=False)
    freeze_authority_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    migrated_from_pumpfun: Mapped[bool] = mapped_column(Boolean, default=False)
    liquidity_pool_size_sol: Mapped[float | None] = mapped_column(Float, nullable=True)


    # === Premium Filters ===
    top10_holders_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    # Optional future metrics:
    # max_same_block_buys: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # safety_check_period_passed: Mapped[bool] = mapped_column(Boolean, default=False)

    # === Analysis Status Flags ===
    passes_basic_filters: Mapped[bool] = mapped_column(Boolean, default=False)
    passes_premium_filters: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    last_checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_notified: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # ... for selling attempts
    sell_attempts: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, default=0)
    last_sell_attempt: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True, default='pending_buy') # Add this too for better tracking


    def __repr__(self):
        return f"<TokenMetadata(mint_address={self.mint_address}, price_usd={self.price_usd})>"





class User(Base):
    __tablename__ = "users"

    # wallet_address as primary key, automatically generated on access
    wallet_address: Mapped[str] = mapped_column(String, primary_key=True, index=True, nullable=False, unique=True)
    
    # Email is optional, only if they plan to subscribe
    email: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True, nullable=True)
    
    # Store the encrypted private key here. VERY IMPORTANT TO ENCRYPT!
    encrypted_private_key: Mapped[str] = mapped_column(String, nullable=False)
    
    
    buy_amount_sol: Mapped[float] = mapped_column(Float, default=0.05) # Example default
    buy_priority_fee_lamports: Mapped[int] = mapped_column(Integer, default=1_000_000) # e.g., 0.001 SOL
    buy_slippage_bps: Mapped[int] = mapped_column(Integer, default=500) # 500 basis points = 5%

    sell_take_profit_pct: Mapped[float] = mapped_column(Float, default=50.0) # 50%
    sell_stop_loss_pct: Mapped[float] = mapped_column(Float, default=10.0) # 10%
    sell_timeout_seconds: Mapped[int] = mapped_column(Integer, default=300) # 5 minutes
    sell_priority_fee_lamports: Mapped[int] = mapped_column(Integer, default=1_000_000)
    sell_slippage_bps: Mapped[int] = mapped_column(Integer, default=500)
    enable_trailing_stop_loss: Mapped[bool] = mapped_column(Boolean, default=False)
    trailing_stop_loss_pct: Mapped[float | None] = mapped_column(Float, nullable=True) # e.g., 5% trail
    # Consider a `bot_enabled: Mapped[bool] = mapped_column(Boolean, default=False)` field too
    

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    premium_start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    premium_end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    subscriptions: Mapped[List["Subscription"]] = relationship(back_populates="user")
    snipes: Mapped[List["Snipe"]] = relationship(back_populates="user")
    trades: Mapped[List["Trade"]] = relationship("Trade", back_populates="user", cascade="all, delete-orphan") # New relationship
    
    # In User model
    custom_rpc_https: Mapped[str | None] = mapped_column(String, nullable=True)
    custom_rpc_wss: Mapped[str | None] = mapped_column(String, nullable=True)
    
    # Basic Filters
    filter_socials_added: Mapped[bool] = mapped_column(Boolean, default=True)
    filter_liquidity_burnt: Mapped[bool] = mapped_column(Boolean, default=True)
    filter_immutable_metadata: Mapped[bool] = mapped_column(Boolean, default=True)
    filter_mint_authority_renounced: Mapped[bool] = mapped_column(Boolean, default=True)
    filter_freeze_authority_revoked: Mapped[bool] = mapped_column(Boolean, default=True)
    filter_pump_fun_migrated: Mapped[bool] = mapped_column(Boolean, default=True)
    filter_check_pool_size_min_sol: Mapped[float] = mapped_column(Float, default=0.5) # Example threshold

    # Premium Filters (apply only if is_premium = True)
    filter_top_holders_max_pct: Mapped[float | None] = mapped_column(Float, nullable=True) # e.g., 20.0 for 20%
    filter_bundled_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filter_max_same_block_buys: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filter_safety_check_period_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    bot_check_interval_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=30) # Example default

    def __repr__(self):
        return f"<User(wallet_address='{self.wallet_address}', email='{self.email}', is_premium={self.is_premium})>"
    
    


class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    user_wallet_address: Mapped[str] = mapped_column(ForeignKey("users.wallet_address"), index=True)
    mint_address: Mapped[str] = mapped_column(String, index=True)
    token_symbol: Mapped[Optional[str]] = mapped_column(String)
    trade_type: Mapped[str] = mapped_column(String) # "buy", "sell", "liquidity_add", "liquidity_remove"
    amount_sol: Mapped[Optional[float]] = mapped_column(Float) # SOL equivalent
    amount_tokens: Mapped[Optional[float]] = mapped_column(Float) # Number of tokens
    price_sol_per_token: Mapped[Optional[float]] = mapped_column(Float) # Price at the time of trade
    price_usd_at_trade: Mapped[Optional[float]] = mapped_column(Float)
    buy_tx_hash: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True)
    sell_tx_hash: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True)
    
    buy_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sell_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    profit_usd: Mapped[Optional[float]] = mapped_column(Float) # For sell trades
    profit_sol: Mapped[Optional[float]] = mapped_column(Float) # For sell trades
    profit_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # Added for sell trades
    log_message: Mapped[Optional[str]] = mapped_column(Text) # Detailed log for the trade

    user: Mapped["User"] = relationship("User", back_populates="trades")

    def __repr__(self):
        return f"<Trade(id='{self.id}', user_wallet_address='{self.user_wallet_address}', type='{self.trade_type}', mint='{self.mint_address}')>"

    
    
    
    

class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False)
    user_wallet_address: Mapped[str] = mapped_column(ForeignKey("users.wallet_address"), nullable=False)
    
    plan_name: Mapped[str] = mapped_column(String, nullable=False) # e.g., "Premium"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True) # For recurring subscriptions or fixed duration
    
    # Store payment gateway specific IDs if needed
    payment_provider_id: Mapped[Optional[str]] = mapped_column(String, nullable=True) # e.g., Stripe customer ID, subscription ID

    # Relationships
    user: Mapped["User"] = relationship(back_populates="subscriptions")

    def __repr__(self):
        return f"<Subscription(id='{self.id}', user_wallet_address='{self.user_wallet_address}', plan_name='{self.plan_name}', is_active={self.is_active})>"
    
    
    
    

class Snipe(Base):
    __tablename__ = "snipes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False)
    user_wallet_address: Mapped[str] = mapped_column(ForeignKey("users.wallet_address"), nullable=False)
    
    token_address: Mapped[str] = mapped_column(String, nullable=False, index=True)
    amount_sol: Mapped[float] = mapped_column(Float, nullable=False) # Amount of SOL to use for the snipe
    slippage: Mapped[float] = mapped_column(Float, default=0.01, nullable=False) # e.g., 0.01 for 1%
    is_buy: Mapped[bool] = mapped_column(Boolean, nullable=False) # True for buy, False for sell
    
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False) # pending, active, completed, failed, cancelled
    transaction_signature: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    profit_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # Optional: track P/L for the snipe
    
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Store logs and other relevant data as JSON
    logs: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False) # List of log entries

    user: Mapped["User"] = relationship(back_populates="snipes")

    def __repr__(self):
        return f"<Snipe(id='{self.id}', token_address='{self.token_address}', status='{self.status}')>"
    
    
    
    
    


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False)
    token_address: Mapped[str] = mapped_column(String, index=True, nullable=False)
    
    # Overall sentiment score (e.g., -1.0 to 1.0)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Detailed AI analysis (OpenAI summary)
    openai_analysis_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Rug check details
    rug_check_result: Mapped[Optional[str]] = mapped_column(String, nullable=True) # "safe", "medium_risk", "high_risk", "unknown"
    rug_check_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True) # Raw JSON from rugcheck.xyz API
    
    # Additional premium checks
    top_10_holders_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lp_locked: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    mint_authority_revoked: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    
    # When the analysis was performed
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<AIAnalysis(id='{self.id}', token_address='{self.token_address}', sentiment_score={self.sentiment_score}, rug_check_result='{self.rug_check_result}')>"
    
    
    
    
    