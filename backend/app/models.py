from datetime import datetime
from typing import List
from typing import Optional
from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer
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


# This table saves the full data gotten directly via Solscan API of the new token gotten from pumpportal
# Updated TokenMetadata with additional Dexscreener fields:
class TokenMetadata(Base):
    __tablename__ = "token_metadata"

    mint_address: Mapped[str] = mapped_column(String, primary_key=True, nullable=False, unique=True)
    supply: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    symbol: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    decimals: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    holder: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    creator: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    create_tx: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    first_mint_tx: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    first_mint_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    volume_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_change_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # New field to store the entry price of a trade.
    entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Fields for candidate analysis:
    is_candidate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_notified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Additional fields from Dexscreener:
    dexscreener_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pair_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    price_native: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    price_usd: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    liquidity: Mapped[Optional[float]] = mapped_column(String, nullable=True)
    market_cap: Mapped[Optional[float]] = mapped_column(String, nullable=True)
    pair_created_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # epoch timestamp
    websites: Mapped[Optional[str]] = mapped_column(String, nullable=True)         # you can store as a JSON-string or comma-separated list
    twitter: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    telegram: Mapped[Optional[str]] = mapped_column(String, nullable=True)


