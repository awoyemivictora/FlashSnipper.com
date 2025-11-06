from pydantic import BaseModel
from datetime import datetime

# Base schema for TokenTrade
class TokenTradeBase(BaseModel):
    mint_address: str
    name: str
    symbol: str
    price_in_usd: float
    volume: float
    timestamp: datetime

# Schema for creating a TokenTrade
class TokenTradeCreate(TokenTradeBase):
    pass

# Response schema for TokenTrade
class TokenTradeResponse(TokenTradeBase):
    id: int

    class Config:
        from_attributes = True  # Use the updated syntax for Pydantic v2

# Base schema for PriceSurge
class PriceSurgeBase(BaseModel):
    mint_address: str
    start_price: float
    end_price: float
    timestamp: datetime

# Schema for creating a PriceSurge
class PriceSurgeCreate(PriceSurgeBase):
    pass

# Response schema for PriceSurge
class PriceSurgeResponse(PriceSurgeBase):
    id: int

    class Config:
        from_attributes = True  # Updated syntax for Pydantic v2
