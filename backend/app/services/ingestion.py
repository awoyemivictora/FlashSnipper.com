#------------- Data Processing and Storage ------------
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import TokenTrade, PriceSurge
from app.utils.bitquery import fetch_bitquery_data


# Bitquery queries
TRADE_QUERY_1H = """
query MyQuery($time_1h_ago: DateTime) {
  Solana {
    DEXTradeByTokens(
      where: {
        Trade: {
          Dex: { ProtocolName: { is: "pump" } }
        }
        Block: { Time: { since: $time_1h_ago } }
      }
    ) {
      Trade {
        Currency {
          Name
          Symbol
          MintAddress
        }
        PriceInUSD
      }
      volume: sum(of: Trade_Side_AmountInUSD)
    }
  }
}
"""

TRADE_QUERY_5MIN = """
graphql
query MyQuery($time_5min_ago: DateTime) {
  Solana {
    DEXTradeByTokens(
      where: {
        Trade: {
          Dex: { ProtocolName: { is: "pump" } }
        }
        Block: { Time: { since: $time_5min_ago } }
      }
    ) {
      Trade {
        Currency {
          MintAddress
        }
        start: PriceInUSD(minimum: Block_Time)
        end: PriceInUSD(maximum: Block_Time)
      }
    }
  }
}
"""


# Functions to store data
def store_trade_data_1h(db: Session, time_1h_ago: str):
    data = fetch_bitquery_data(TRADE_QUERY_1H, {"time_1h_ago": time_1h_ago})
    trades = data["data"]["Solana"]["DEXTradeByTokens"]

    for trade in trades:
        currency = trade["Trade"]["Currency"]
        token_trade = TokenTrade(
            mint_address=currency["MintAddress"],
            name=currency["Name"],
            symbol=currency["Symbol"],
            price_in_usd=trade["Trade"]["PriceInUSD"],
            volume=trade["volume"],
            timestamp=datetime.utcnow(),
        )
        db.merge(token_trade) # Use `merge` to upsert
    db.commit()


def store_price_surge_data(db: Session, time_5min_ago: str):
    data = fetch_bitquery_data(TRADE_QUERY_5MIN, {"time_5min_ago": time_5min_ago})
    surges = data["data"]["Solana"]["DEXTradeByTokens"]

    for surge in surges:
        token_surge = PriceSurge(
            mint_address=surge["Trade"]["Currency"]["MintAddress"],
            start_price=surge["Trade"]["start"],
            end_price=surge["Trade"]["end"],
            timestamp=datetime.utcnow(),
        )
        db.add(token_surge)
    db.commit()



