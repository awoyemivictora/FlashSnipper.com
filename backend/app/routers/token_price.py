from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import TokenTrade, PriceSurge
from app.schemas import TokenTradeCreate, PriceSurgeCreate


router = APIRouter(prefix="/market-data", tags=["Market Data"])

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






























from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from gql import gql, Client
from gql.transport.websockets import WebsocketsTransport
from datetime import datetime, timedelta
import asyncio
import os
from dotenv import load_dotenv
import requests

load_dotenv()

from . import models, database


BITQUERY_WS_URL = "wss://streaming.bitquery.io/eap?token=ory_at_Xy8UlzvVEe9MimhKD39NzfvQlLnnA_seAcSQcxFdNE0.UVoMWADx1s5gVFi17LwoQk0dFcjeBAZNbIuShTEg36A"


# Database setup
models.Base.metadata.create_all(bind=database.engine)


async def bitquery_subscription_loop():
    """
    Runs the Bitquery subscription every 30 seconds.
    """
    while True:
        try:
          await start_bitquery_subscription()
        except Exception as e:
            print(f"Bitquery subscription error: {e}")
        await asyncio.sleep(30) # Wait for 30 seconds before restarting


async def start_bitquery_subscription():
    """
    Subscribes to Bitquery's WebSocket feed and processes real-time data.
    """
    transport = WebsocketsTransport(
        url=BITQUERY_WS_URL,
        headers={"Sec-WebSocket-Protocol": "graphql-ws"},
    )
    await transport.connect()
    print("Connected to Bitquery WebSocket")

    query = gql(
      """
       query MyQuery($time_1h_ago: DateTime, $token: String, $side: String) {
        Solana {
            volume: DEXTradeByTokens(
            where: {
                Trade: {
                Currency: { MintAddress: { is: $token } }
                Side: { Currency: { MintAddress: { is: $side } } }
                }
                Block: { Time: { since: $time_1h_ago } }
            }
            ) {
            sum(of: Trade_Side_AmountInUSD)
            }
            liquidity: DEXPools(
            where: {
                Pool: {
                Market: {
                    BaseCurrency: { MintAddress: { is: $token } }
                    QuoteCurrency: { MintAddress: { is: $side } }
                }
                }
                Block: { Time: { till: $time_1h_ago } }
            }
            limit: { count: 1 }
            orderBy: { descending: Block_Time }
            ) {
            Pool {
                Base {
                PostAmountInUSD
                }
            }
            }
            marketcap: TokenSupplyUpdates(
            where: {
                TokenSupplyUpdate: { Currency: { MintAddress: { is: $token } } }
                Block: { Time: { till: $time_1h_ago } }
            }
            limitBy: { by: TokenSupplyUpdate_Currency_MintAddress, count: 1 }
            orderBy: { descending: Block_Time }
            ) {
            TokenSupplyUpdate {
                PostBalanceInUSD
                Currency {
                Name
                MintAddress
                Symbol
                }
            }
            }
            }
        }
      """
    )

    async def process_subscription():
        try:
            async for result in transport.subscribe(query):
                await handle_bitquery_data(result)
        except asyncio.CancelledError:
            print("Bitquery subscription cancelled.")
        finally:
            await transport.close()

    # Run the subscription in a task
    asyncio.create_task(process_subscription())





async def handle_bitquery_data(data):
    """
    Processes Bitquery WebSocket data and stores it in the database.
    """
    # Check if the 'data' attribute exists and is not None
    if hasattr(data, 'data') and data.data:
        solana_data = data.data.get("Solana", {}).get("DEXTradeByTokens", [])
        
        with database.SessionLocal() as db:
            for trade in solana_data:
                currency = trade["Trade"]["Currency"]
                token_trade = models.TokenTrade(
                    mint_address=currency["MintAddress"],
                    name=currency["Name"],
                    symbol=currency["Symbol"],
                    price_in_usd=trade["Trade"]["PriceInUSD"],
                    volume=trade["volume"],
                    timestamp=datetime.utcnow(),
                )
                # Upsert the record in the database
                upsert_token_trade(db, token_trade)



def upsert_token_trade(db: Session, token_trade: models.TokenTrade):
    """
    Updates or inserts a TokenTrade record in the database.
    """
    existing_trade = db.query(models.TokenTrade).filter_by(
        mint_address=token_trade.mint_address
    ).first()
    if existing_trade:
        existing_trade.price_in_usd = token_trade.price_in_usd
        existing_trade.volume = token_trade.volume
        existing_trade.updated_at = datetime.utcnow()
    else:
        db.add(token_trade)
    db.commit()



@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan manager for FastAPI application.
    """
    print("Starting up...")
    # Start the Bitquery subscription
    asyncio.create_task(bitquery_subscription_loop()) # Start 30-second loop
    yield
    # Cleanup logic (if needed)
    print('Shutting down...')


app = FastAPI(lifespan=lifespan)


@app.get("/")
def root():
    return {"status": "API is running"}















import requests

def filter_tokens(data):
    filtered_tokens = []

    for trade in data.get("Solana", {}).get("DEXTradeByTokens", []):
        token_info = trade["Trade"]["Currency"]
        volume_5min = float(trade["traded_volume_5min"])
        buyers_5min = int(trade["buyers_5min"])
        start_price = float(trade["Trade"]["start"])
        end_price = float(trade["Trade"]["end"])

        # 1. Volume Check (Below 15K in last hour)
        if volume_5min > 15000:
            continue

        # 2. Market Cap Check (You need an external API to fetch Market Cap)
        # market_cap = get_market_cap(token_info["MintAddress"])  # Placeholder
        # if not (20000 <= market_cap <= 150000):
        #     continue

        # 3. Price Surge Check (50% increase in last 5 min)
        price_surge = ((end_price / start_price) - 1) * 100
        if price_surge < 50:
            continue

        # 4. Holders Surge Check (+10 new holders in last 5 min)
        if buyers_5min < 10:
            continue

        # 5. Deployment Age Check (Need external API for timestamp)
        # deployment_time = get_token_creation_time(token_info["MintAddress"])
        # if not (15 * 60 <= (current_time - deployment_time) <= 72 * 3600):
        #     continue

        # If all conditions pass, add the token to the filtered list
        filtered_tokens.append({
            "symbol": token_info["Symbol"].strip(),
            "name": token_info["Name"].strip(),
            "mint_address": token_info["MintAddress"],
            "volume_5min": volume_5min,
            "price_surge": price_surge,
            "holders_surge": buyers_5min
        })

    return filtered_tokens

# Example Usage
bitquery_data = { 
    "Solana": {
        "DEXTradeByTokens": [
            {
                "Trade": {
                    "Currency": {
                        "MintAddress": "2qEHjDLDLbuBgRYvsxhc5D6uDWAivNFZGan56P1tpump",
                        "Name": "Peanut the Squirrel",
                        "Symbol": "Pnut"
                    },
                    "end": 0.202,
                    "start": 0.133
                },
                "traded_volume_5min": "12000",
                "buyers_5min": "12"
            }
        ]
    }
}

filtered = filter_tokens(bitquery_data)
print(filtered)
