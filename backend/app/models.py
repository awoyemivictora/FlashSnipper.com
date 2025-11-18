# app/models.py
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, List


class Base(DeclarativeBase):
    pass


# ──────────────────────────────────────────────────────────────
# 1. New Tokens & Metadata (shared across all users)
# ──────────────────────────────────────────────────────────────
class NewTokens(Base):
    __tablename__ = "new_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mint_address: Mapped[str] = mapped_column(String, index=True)
    pool_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    signature: Mapped[str] = mapped_column(String)
    tx_type: Mapped[str] = mapped_column(String)
    metadata_status: Mapped[str] = mapped_column(String, default="pending")


class TokenMetadata(Base):
    __tablename__ = "token_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mint_address: Mapped[str] = mapped_column(String, unique=True, index=True)
    dexscreener_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pair_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    price_native: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    market_cap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pair_created_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    websites: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    twitter: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    telegram: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    token_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    token_symbol: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    dex_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    volume_h24: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_h6: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_h1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_m5: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_change_h1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_change_m5: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_change_h6: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_change_h24: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    socials_present: Mapped[bool] = mapped_column(Boolean, default=False)
    liquidity_burnt: Mapped[bool] = mapped_column(Boolean, default=False)
    liquidity_pool_size_sol: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    immutable_metadata: Mapped[bool] = mapped_column(Boolean, default=False)
    mint_authority_renounced: Mapped[bool] = mapped_column(Boolean, default=False)
    freeze_authority_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    token_decimals: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    holder: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    top10_holders_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    webacy_risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    webacy_risk_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    webacy_moon_potential: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


# ──────────────────────────────────────────────────────────────
# 2. User + One-to-Many → Trades (THIS IS THE KEY)
# ──────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    wallet_address: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    encrypted_private_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    premium_start_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    premium_end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Custom RPCs
    custom_rpc_https: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    custom_rpc_wss: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Bot Filters (Free users get limited, Premium gets all)
    filter_socials_added: Mapped[bool] = mapped_column(Boolean, default=True)
    filter_liquidity_burnt: Mapped[bool] = mapped_column(Boolean, default=True)
    filter_immutable_metadata: Mapped[bool] = mapped_column(Boolean, default=True)
    filter_mint_authority_renounced: Mapped[bool] = mapped_column(Boolean, default=True)
    filter_freeze_authority_revoked: Mapped[bool] = mapped_column(Boolean, default=True)
    filter_check_pool_size_min_sol: Mapped[float] = mapped_column(Float, default=10.0)
    filter_top_holders_max_pct: Mapped[float] = mapped_column(Float, default=30.0)
    filter_safety_check_period_seconds: Mapped[int] = mapped_column(Integer, default=300)

    # Trading Settings
    buy_amount_sol: Mapped[float] = mapped_column(Float, default=0.1)
    buy_slippage_bps: Mapped[int] = mapped_column(Integer, default=1000)
    sell_take_profit_pct: Mapped[float] = mapped_column(Float, default=50.0)
    sell_stop_loss_pct: Mapped[float] = mapped_column(Float, default=20.0)
    sell_timeout_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    trailing_stop_loss_pct: Mapped[float] = mapped_column(Float, default=10.0)
    bot_check_interval_seconds: Mapped[int] = mapped_column(Integer, default=10)

    # Relationship: One User → Many Trades
    trades: Mapped[List["Trade"]] = relationship("Trade", back_populates="user", cascade="all, delete-orphan")


# ──────────────────────────────────────────────────────────────
# 3. Trade (belongs to ONE user)
# ──────────────────────────────────────────────────────────────
class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_wallet_address: Mapped[str] = mapped_column(
        ForeignKey("users.wallet_address", ondelete="CASCADE"), index=True
    )

    mint_address: Mapped[str] = mapped_column(String, index=True)
    token_symbol: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    trade_type: Mapped[str] = mapped_column(String)  # "buy" or "sell"
    amount_sol: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    amount_tokens: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_sol_per_token: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_usd_at_trade: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    buy_tx_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sell_tx_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    profit_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    profit_sol: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    log_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    buy_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    token_amounts_purchased: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    token_decimals: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sell_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    swap_provider: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    buy_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sell_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationship back to User
    user: Mapped["User"] = relationship("User", back_populates="trades")


# ──────────────────────────────────────────────────────────────
# 4. Subscription (optional, for Stripe/PayPal later)
# ──────────────────────────────────────────────────────────────
class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_wallet_address: Mapped[str] = mapped_column(
        ForeignKey("users.wallet_address", ondelete="CASCADE"), index=True
    )
    plan_name: Mapped[str] = mapped_column(String)
    payment_provider_id: Mapped[str] = mapped_column(String)
    start_date: Mapped[datetime] = mapped_column(DateTime)
    end_date: Mapped[datetime] = mapped_column(DateTime)
    
    
    
    