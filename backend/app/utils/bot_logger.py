# app/utils/bot_logger.py
import sys
import json
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Create a separate WebSocket manager for the logger
class BotLoggerWebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, any] = {}  # Use 'any' to avoid type issues
    
    async def connect(self, websocket, wallet_address: str):
        await websocket.accept()
        self.active_connections[wallet_address] = websocket
    
    def disconnect(self, wallet_address: str):
        if wallet_address in self.active_connections:
            del self.active_connections[wallet_address]
    
    async def send_personal_message(self, message: str, wallet_address: str):
        if wallet_address in self.active_connections:
            try:
                await self.active_connections[wallet_address].send_text(message)
            except Exception as e:
                logging.error(f"Error sending message to {wallet_address}: {e}")
                self.disconnect(wallet_address)

# Create global instance
websocket_manager = BotLoggerWebSocketManager()

class BotLogger:
    def __init__(self, wallet_address: str):
        self.wallet_address = wallet_address
    
    async def send_log(self, message: str, log_type: str = "info", tx_hash: str = None, token_symbol: str = None):
        """Send formatted log to frontend"""
        log_data = {
            "type": "log",
            "log_type": log_type,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "wallet_address": self.wallet_address,
            "token_symbol": token_symbol,
            "tx_hash": tx_hash
        }
        
        if tx_hash:
            log_data["explorer_urls"] = {
                "solscan": f"https://solscan.io/tx/{tx_hash}",
                "dexScreener": f"https://dexscreener.com/solana/{tx_hash}",
                "jupiter": f"https://jup.ag/tx/{tx_hash}"
            }
        
        await websocket_manager.send_personal_message(
            json.dumps(log_data),
            self.wallet_address
        )
        logger.info(f"[{self.wallet_address}] {log_type.upper()}: {message}")

# Predefined log templates
class LogTemplates:
    @staticmethod
    def bot_started():
        return "<strong>Starting to observe new token launches</strong>"
    
    @staticmethod
    def new_pool_detected(dex: str, token_symbol: str):
        return f"<strong>New Pool Detected on {dex}</strong>"
    
    @staticmethod
    def waiting_for_conditions():
        return "<strong>Waiting for coin to meet your bot settings logics...</strong>"
    
    @staticmethod
    def attempting_buy(token_symbol: str):
        return f"<strong>Attempting to buy <strong>{token_symbol}</strong>...</strong>"
    
    @staticmethod
    def send_sell_attempt():
        return "<strong>Send sell transaction attempt</strong>"
    
    @staticmethod
    def transaction_executed():
        return "<strong>Transaction executed. Starting confirmation process</strong>"
    
    @staticmethod
    def transaction_confirmed():
        return "<strong>Transaction Confirmed</strong>"
    
    @staticmethod
    def sell_confirmed(tx_hash: str):
        return f'Sell transaction confirmed. View transaction on <a href="https://solscan.io/tx/{tx_hash}" target="_blank">Solscan</a> <a href="https://dexscreener.com/solana/{tx_hash}" target="_blank">Dexscreener</a> <a href="https://jup.ag/tx/{tx_hash}" target="_blank">Jupiter</a>'

def get_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    # File handler (optional, good for persistent logs)
    fh = logging.FileHandler('solsniper.log')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    return logger

