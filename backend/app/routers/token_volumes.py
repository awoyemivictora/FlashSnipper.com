from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import TokenTrade, PriceSurge
from app.schemas import TokenTradeCreate, PriceSurgeCreate


router = APIRouter(prefix="/token-volume", tags=["Token Volume"])

@router.post("/token-trades/", response_model=TokenTradeCreate)
def add_token_trade(trade: TokenTradeCreate, db: Session = Depends(get_db)):
    db_trade = TokenTrade(**trade.dict())
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)
    return db_trade

@router.post("/price-surges/", response_model=PriceSurgeCreate)
def add_price_surge(surge: PriceSurgeCreate, db: Session = Depends(get_db)):
    db_surge = PriceSurge(**surge.dict())
    db.add(db_surge)
    db.commit()
    db.refresh(db_surge)
    return db_surge


