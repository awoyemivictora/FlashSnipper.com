import re
import os
from dotenv import load_dotenv
import requests
import aiohttp
import asyncio

load_dotenv()

# Read Telegram config from env variables
TELEGRAM_BOT_TOKENS = [
    os.getenv("TELEGRAM_BOT_TOKEN_ME"),  # For you
    os.getenv("TELEGRAM_BOT_TOKEN_CLIENT")  # For client
]

TELEGRAM_CHAT_IDS = [
    os.getenv("TELEGRAM_CHAT_ID_ME"),  # For you
    os.getenv("TELEGRAM_CHAT_ID_CLIENT")  # For client
]

def escape_markdown(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)


async def send_telegram_notification(token):
    """
    Sends a Telegram notification with candidate token details.
    """
    if not token or not hasattr(token, "mint_address"):
        print("Invalid token object. Skipping Telegram notification.")
        return False  # Return False instead of None

    message = format_telegram_message(token)
    if not message:
        print(f"Failed to format Telegram message for {token}")
        return False

    # Create an asynchronous session to send notifications to both bots
    async with aiohttp.ClientSession() as session:
        try:
            tasks = []
            for bot_token, chat_id in zip(TELEGRAM_BOT_TOKENS, TELEGRAM_CHAT_IDS):
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                tasks.append(session.post(url, data=payload))  # Create task for each bot

            # Send all requests concurrently
            responses = await asyncio.gather(*tasks)

            for response in responses:
                response.raise_for_status()  # Check if the request was successful
            print(f"Telegram notification sent for token: {token.mint_address}")
            return True  # Ensure function returns success status

        except aiohttp.ClientResponseError as e:
            print(f"HTTP error sending Telegram notification for {token.mint_address}: {e.status} {e.message}")
        except Exception as e:
            print(f"Error sending Telegram notification for {token.mint_address}: {e}")

    return False  # Ensure it always returns a boolean



def format_telegram_message(token) -> str:
    if not token or not hasattr(token, "mint_address"):
        return ""

    solscan_token_url = f"https://solscan.io/token/{token.mint_address}"
    pumpfun_url = f"https://pump.fun/coin/{token.mint_address}"
    solscan_creator_url = f"https://solscan.io/account/{token.creator}" if hasattr(token, 'creator') and token.creator else "N/A"
    dex_url = token.dexscreener_url if hasattr(token, 'dexscreener_url') and token.dexscreener_url else "N/A"
    timestamp_str = token.timestamp.strftime('%Y-%m-%d %H:%M:%S') if hasattr(token, 'timestamp') and token.timestamp else "N/A"

    return f"""
    🔥 <b>New Qualified Pumpfun Token Detected</b>
    ---------------------------------
    🟢 <b>Token Name</b>: {token.name if hasattr(token, 'name') and token.name else 'Unknown'}
    🔵 <b>Token Symbol</b>: {token.symbol if hasattr(token, 'symbol') and token.symbol else 'Unknown'}
    🔑 <b>Token Address</b>: <a href="{pumpfun_url}">{token.mint_address}</a> | <a href="{solscan_token_url}">Solscan</a>
    👤 <b>Creator</b>: <a href="{solscan_creator_url}">{token.creator if hasattr(token, 'creator') and token.creator else 'N/A'}</a>
    🔗 <b>Dexscreener URL</b>: <a href="{dex_url}">{dex_url if hasattr(token, 'dexscreener_url') and token.dexscreener_url else 'N/A'}</a>
    📜 <b>Pair Address</b>: {token.pair_address if hasattr(token, 'pair_address') and token.pair_address else 'N/A'}
    💰 <b>Price (Native)</b>: {token.price_native if hasattr(token, 'price_native') and token.price_native else 'N/A'}
    💵 <b>Price (USD)</b>: {token.price_usd if hasattr(token, 'price_usd') and token.price_usd else 'N/A'}
    🏦 <b>Market Cap</b>: {token.market_cap if hasattr(token, 'market_cap') and token.market_cap is not None else 'N/A'}
    ⏰ <b>Pair Created At</b>: {token.pair_created_at if hasattr(token, 'pair_created_at') and token.pair_created_at else 'N/A'}
    🌐 <b>Websites</b>: {token.holder if hasattr(token, 'holder') and token.holder else 'N/A'}
    📅 <b>Timestamp</b>: {timestamp_str}
    ---------------------------------
    🌐 <i>Tracking new tokens for exciting opportunities!</i>
    """






# ------------------------------- For Buying Token
# async def send_buy_telegram_notification(token):
#     """
#     Sends a BUY Telegram notification with candidate token details.
#     """
#     if not token or not hasattr(token, "mint_address"):
#         print("Invalid token object. Skipping Telegram BUY notification.")
#         return False  # Return False instead of None

#     message = format_telegram_message_buy(token)
#     if not message:
#         print(f"Failed to format Telegram message for {token}")
#         return False

#     url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
#     payload = {
#         "chat_id": TELEGRAM_CHAT_ID,
#         "text": message,
#         "parse_mode": "HTML"
#     }

#     async with aiohttp.ClientSession() as session:
#         try:
#             async with session.post(url, data=payload) as response:
#                 response.raise_for_status()
#                 print(f"Telegram BUY notification sent for token: {token.mint_address}")
#                 return True  # Ensure function returns success status
#         except aiohttp.ClientResponseError as e:
#             print(f"HTTP error sending Telegram BUY notification for {token.mint_address}: {e.status} {e.message}")
#         except Exception as e:
#             print(f"Error sending Telegram BUY notification for {token.mint_address}: {e}")
    
#     return False  # Ensure it always returns a boolean


async def send_buy_telegram_notification(token):
    """
    Sends a BUY Telegram notification with candidate token details.
    """
    if not token or not hasattr(token, "mint_address"):
        print("Invalid token object. Skipping Telegram BUY notification.")
        return False  # Return False instead of None

    message = format_telegram_message_buy(token)
    if not message:
        print(f"Failed to format Telegram message for {token}")
        return False

    # Create an asynchronous session to send notifications to both bots
    async with aiohttp.ClientSession() as session:
        try:
            tasks = []
            for bot_token, chat_id in zip(TELEGRAM_BOT_TOKENS, TELEGRAM_CHAT_IDS):
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                tasks.append(session.post(url, data=payload))  # Create task for each bot

            # Send all requests concurrently
            responses = await asyncio.gather(*tasks)

            for response in responses:
                response.raise_for_status()  # Check if the request was successful
            print(f"Telegram BUY notification sent for token: {token.mint_address}")
            return True  # Ensure function returns success status

        except aiohttp.ClientResponseError as e:
            print(f"HTTP error sending Telegram BUY notification for {token.mint_address}: {e.status} {e.message}")
        except Exception as e:
            print(f"Error sending Telegram BUY notification for {token.mint_address}: {e}")

    return False  # Ensure it always returns a boolean


def format_telegram_message_buy(token) -> str:
    if not token or not hasattr(token, "mint_address"):
        return ""

    solscan_token_url = f"https://solscan.io/token/{token.mint_address}"
    pumpfun_url = f"https://pump.fun/coin/{token.mint_address}"
    solscan_creator_url = f"https://solscan.io/account/{token.creator}" if hasattr(token, 'creator') and token.creator else "N/A"
    dex_url = token.dexscreener_url if hasattr(token, 'dexscreener_url') and token.dexscreener_url else "N/A"
    timestamp_str = token.timestamp.strftime('%Y-%m-%d %H:%M:%S') if hasattr(token, 'timestamp') and token.timestamp else "N/A"

    return f"""
    ✅ <b>Buy Trade Successful!</b>
    ---------------------------------
    🟢 <b>Token Name</b>: {token.name if hasattr(token, 'name') and token.name else 'Unknown'}
    🔵 <b>Token Symbol</b>: {token.symbol if hasattr(token, 'symbol') and token.symbol else 'Unknown'}
    🔑 <b>Token Address</b>: <a href="{pumpfun_url}">{token.mint_address}</a> | <a href="{solscan_token_url}">Solscan</a>
    🔵 <b>Entry Price</b>: {token.entry_price if hasattr(token, 'entry_price') and token.entry_price else 'Unknown'}
    📈 <b>Amount Purchased</b>: 100 {token.symbol if hasattr(token, 'symbol') and token.symbol else 'tokens'}
    📅 <b>Timestamp</b>: {timestamp_str}
    ---------------------------------
    🌐 <i>Monitoring token for SL/TP!</i>
    """








# ------------------------------- For Selling Token
# async def send_sell_telegram_notification(token, profit):
#     """
#     Sends a SELL Telegram notification with candidate token and profit details.
#     """
#     if not token or not hasattr(token, "mint_address"):
#         print("Invalid token object. Skipping Telegram SELL notification.")
#         return False  # Return False instead of None

#     message = format_telegram_message_sell(token, profit)
#     if not message:
#         print(f"Failed to format Telegram message for {token}")
#         return False

#     url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
#     payload = {
#         "chat_id": TELEGRAM_CHAT_ID,
#         "text": message,
#         "parse_mode": "HTML"
#     }

#     async with aiohttp.ClientSession() as session:
#         try:
#             async with session.post(url, data=payload) as response:
#                 response.raise_for_status()
#                 print(f"Telegram SELL notification sent for token: {token.mint_address}")
#                 return True  # Ensure function returns success status
#         except aiohttp.ClientResponseError as e:
#             print(f"HTTP error sending Telegram SELL notification for {token.mint_address}: {e.status} {e.message}")
#         except Exception as e:
#             print(f"Error sending Telegram SELL notification for {token.mint_address}: {e}")
    
#     return False  # Ensure it always returns a boolean


async def send_sell_telegram_notification(token, profit):
    """
    Sends a SELL Telegram notification with candidate token and profit details.
    """
    if not token or not hasattr(token, "mint_address"):
        print("Invalid token object. Skipping Telegram SELL notification.")
        return False  # Return False instead of None

    message = format_telegram_message_sell(token, profit)
    if not message:
        print(f"Failed to format Telegram message for {token}")
        return False

    # Create an asynchronous session to send notifications to both bots
    async with aiohttp.ClientSession() as session:
        try:
            tasks = []
            for bot_token, chat_id in zip(TELEGRAM_BOT_TOKENS, TELEGRAM_CHAT_IDS):
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                tasks.append(session.post(url, data=payload))  # Create task for each bot

            # Send all requests concurrently
            responses = await asyncio.gather(*tasks)

            for response in responses:
                response.raise_for_status()  # Check if the request was successful
            print(f"Telegram SELL notification sent for token: {token.mint_address}")
            return True  # Ensure function returns success status

        except aiohttp.ClientResponseError as e:
            print(f"HTTP error sending Telegram SELL notification for {token.mint_address}: {e.status} {e.message}")
        except Exception as e:
            print(f"Error sending Telegram SELL notification for {token.mint_address}: {e}")

    return False  # Ensure it always returns a boolean


def format_telegram_message_sell(token, profit) -> str:
    if not token or not hasattr(token, "mint_address"):
        return ""

    solscan_token_url = f"https://solscan.io/token/{token.mint_address}"
    pumpfun_url = f"https://pump.fun/coin/{token.mint_address}"
    solscan_creator_url = f"https://solscan.io/account/{token.creator}" if hasattr(token, 'creator') and token.creator else "N/A"
    dex_url = token.dexscreener_url if hasattr(token, 'dexscreener_url') and token.dexscreener_url else "N/A"
    timestamp_str = token.timestamp.strftime('%Y-%m-%d %H:%M:%S') if hasattr(token, 'timestamp') and token.timestamp else "N/A"

    return f"""
     <b>SELL Trade Successful!</b>
    ---------------------------------
    🟢 <b>Token Name</b>: {token.name if hasattr(token, 'name') and token.name else 'Unknown'}
    🔵 <b>Token Symbol</b>: {token.symbol if hasattr(token, 'symbol') and token.symbol else 'Unknown'}
    🔑 <b>Token Address</b>: <a href="{pumpfun_url}">{token.mint_address}</a> | <a href="{solscan_token_url}">Solscan</a>
    🔵 <b>Entry Price</b>: {token.entry_price if hasattr(token, 'entry_price') and token.entry_price else 'Unknown'}
    ✅ <b>Profit</b>: ${profit:.2f} USD
    📅 <b>Timestamp</b>: {timestamp_str}
    """



