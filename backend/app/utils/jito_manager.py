import json 
import logging 
from typing import Dict, Optional, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.transaction import VersionedTransaction
from solana.rpc.async_api import AsyncClient
import base58
import aiohttp

from app.models import User
from app.config import settings

logger = logging.getLogger(__name__)

class JitoTipManager:
    """Manages Jito tip accounts for users"""
    
    def __init__(self):
        self.JITO_TIP_AMOUNT_PER_TX = 100_000   # 0.0001 SOL per transaction
        self.MIN_RESERVED_TIP_AMOUNT = 0.01     # Minimum 0.01 SOL to reserve
        self.TIP_ACCOUNT_UPDATE_URL = "https://mainnet.block-engine.jito.wtf/api/v1/bundles"
        
    async def get_or_create_tip_account(
        self,
        user: User,
        db: AsyncSession,
        connection: AsyncClient
    ) -> Tuple[str, bool]:
        """
        Get existing tip account or create a new one for the user.
        Returns (tip_account_public_key, is_new_account)
        """
        try:
            # First check if user already has a tip account in database
            if user.jito_tip_account:
                logger.info(f"User {user.wallet_address[:8]} already has tip account in DB: {user.jito_tip_account}")
                
                # Check if the account exists on-chain and has balance
                try:
                    balance_response = await connection.get_balance(Pubkey.from_string(user.jito_tip_account))
                    balance = balance_response.value if hasattr(balance_response, 'value') else 0
                    
                    if balance > 0:
                        logger.info(f"Tip account exists on-chain with balance: {balance/1_000_000_000:.6f} SOL")
                        return user.jito_tip_account, False
                    else:
                        logger.info(f"Tip account exists but has zero balance, keeping existing account")
                        # Even if balance is 0, return the existing account
                        return user.jito_tip_account, False
                except Exception as e:
                    logger.warning(f"Could not verify tip account on-chain: {e}. Using existing account from DB.")
                    # If we can't verify on-chain, still return the existing account
                    return user.jito_tip_account, False
            
            # Create new tip account keypair
            tip_keypair = Keypair()
            tip_account_pubkey = str(tip_keypair.pubkey())
            
            # Update user record
            user.jito_tip_account = tip_account_pubkey
            user.jito_tip_account_initialized = False   # Will be true after funding
            user.jito_current_tip_balance = 0.0
            
            await db.commit()
            logger.info(f"Created new Jito tip account for user {user.wallet_address[:8]}: {tip_account_pubkey}")
            
            return tip_account_pubkey, True 
        
        except Exception as e:
            logger.error(f"Failed to get/create tip account for {user.wallet_address[:8]}: {e}")
            await db.rollback()
            raise
    
    async def fund_tip_account(
        self,
        user: User,
        db: AsyncSession,
        connection: AsyncClient,
        amount_sol: Optional[float] = None 
    ) -> bool:
        """
        Fund the user's tip account from their main wallet.
        If amount is None, uses user.jito_reserved_tip_amount.
        """
        try:
            if not user.jito_tip_account:
                raise ValueError("User has no tip account")

            # Determine amount to transfer
            transfer_amount_sol = amount_sol or user.jito_reserved_tip_amount
            if transfer_amount_sol <= 0:
                raise ValueError("Transfer amount must be positive")
            
            # Convert SOL to lamports
            transfer_lamports = int(transfer_amount_sol * 1_000_000_000)
            
            # Check user's main wallet balance - FIXED: extract value from response
            balance_response = await connection.get_balance(Pubkey.from_string(user.wallet_address))
            user_balance = balance_response.value if balance_response.value else 0
            
            if user_balance < transfer_lamports:
                logger.error(f"Insufficient balance for {user.wallet_address[:8]}: {user_balance/1e9:.4f} SOL < {transfer_amount_sol} SOL")
                return False 
            
            # Create transfer instruction
            transfer_ix = transfer(
                TransferParams(
                    from_pubkey=Pubkey.from_string(user.wallet_address),
                    to_pubkey=Pubkey.from_string(user.jito_tip_account),
                    lamports=transfer_lamports
                )
            )
            
            # Get recent blockhash
            recent_blockhash = (await connection.get_latest_blockhash()).value.blockhash
            
            # Create transaction (user will sign on frontend)
            message = VersionedTransaction(
                [transfer_ix],
                [Pubkey.from_string(user.wallet_address)],
                recent_blockhash
            )
            
            # Serialize transaction for frontend
            serialized_tx = bytes(message).hex()
            
            # Update user record
            user.jito_current_tip_balance = transfer_amount_sol
            user.jito_tip_account_initialized = True 
            user.jito_tip_last_updated = datetime.utcnow()
            await db.commit()
            
            logger.info(f"Prepared tip account funding for {user.wallet_address[:8]}: {transfer_amount_sol} SOL")
            
            return True 
        
        except Exception as e:
            logger.error(f"Failed to fund tip account for {user.wallet_address[:8]}: {e}")
            await db.rollback()
            return False 
        
    async def deduct_tip_from_balance(
        self,
        user: User,
        db: AsyncSession,
        connection: AsyncClient,
        num_transactions: int = 1
    ) -> bool:
        """
        Deduct tip amount from user's tip account balance.
        Called after successful transaction execution.
        """
        try:
            if not user.jito_tip_account:
                logger.warning(f"No tip account for {user.wallet_address[:8]}")
                return False 

            # Calculate total tip for transactions
            total_tip_lamports = user.jito_tip_per_tx * num_transactions
            total_tip_sol = total_tip_lamports / 1_000_000_000
            
            # Check tip account balance - FIXED: extract value from response
            balance_response = await connection.get_balance(Pubkey.from_string(user.jito_tip_account))
            tip_balance_sol = balance_response.value / 1_000_000_000 if balance_response.value else 0.0
            
            if tip_balance_sol < total_tip_sol:
                logger.warning(f"Insufficient tip balance for {user.wallet_address[:8]}: {tip_balance_sol:.6f} SOL < {total_tip_sol:.6f} SOL")
                
                # Auto-refill if possible
                await self.auto_refill_tip_account(user, db, connection)
                return False
            
            # Update user's tip balance in database
            user.jito_current_tip_balance = tip_balance_sol - total_tip_sol
            user.jito_tip_last_updated = datetime.utcnow()
            await db.commit()
            
            logger.info(f"Deducted {total_tip_sol:.6f} SOL from tip account for {user.wallet_address[:8]}")
            return True 
        
        except Exception as e:
            logger.error(f"Failed to deduct tip for {user.wallet_address[:8]}: {e}")
            return False 
        
    async def auto_refill_tip_account(
        self,
        user: User,
        db: AsyncSession,
        connection: AsyncClient
    ) -> bool:
        """
        Automatically refill tip account from main wallet if needed.
        """
        try:
            # Get current tip balance - FIXED: use proper balance check
            if user.jito_tip_account:
                balance_response = await connection.get_balance(Pubkey.from_string(user.jito_tip_account))
                current_balance = balance_response.value / 1_000_000_000 if balance_response.value else 0.0
            else:
                current_balance = 0.0
            
            # Check if auto-refill should happen
            if current_balance < (user.jito_reserved_tip_amount * 0.2):   # Below 20% of reserved
                refill_amount = user.jito_reserved_tip_amount - current_balance
                
                if refill_amount > 0:
                    logger.info(f"Auto-refilling tip account for {user.wallet_address[:8]}: {refill_amount:.4f} SOL")
                    return await self.fund_tip_account(user, db, connection, refill_amount)
            
            return False 
            
        except Exception as e:
            logger.error(f"Auto-refill failed for {user.wallet_address[:8]}: {e}")
            return False 
        
    async def get_tip_account_info(
        self,
        user: User,
        connection: AsyncClient
    ) -> Dict:
        """
        Get current tip account information.
        """
        try:
            if not user.jito_tip_account:
                return {
                    "has_tip_account": False,
                    "current_balance": 0.0,
                    "reserved_amount": user.jito_reserved_tip_amount,
                    "tip_per_tx": user.jito_tip_per_tx,
                    "status": "not_initialized"
                }
                
            # Get live balance - FIXED: extract value from response
            balance_response = await connection.get_balance(Pubkey.from_string(user.jito_tip_account))
            tip_balance_sol = balance_response.value / 1_000_000_000 if balance_response.value else 0.0
            
            return {
                "has_tip_account": True,
                    "tip_account": user.jito_tip_account,
                    "current_balance": tip_balance_sol,
                    "database_balance": user.jito_current_tip_balance,
                    "reserved_amount": user.jito_reserved_tip_amount,
                    "tip_per_tx": user.jito_tip_per_tx,
                    "initialized": user.jito_tip_account_initialized,
                    "last_updated": user.jito_tip_last_updated.isoformat() if user.jito_tip_last_updated else None,
                    "status": "active" if tip_balance_sol > 0 else "needs_funding"
                }
                
        except Exception as e:
            logger.error(f"Failed to get tip account info for {user.wallet_address[:8]}: {e}")
            return {"error": str(e)}
        
    async def update_tip_settings(
        self,
        user: User,
        db: AsyncSession,
        reserved_amount: float,
        tip_per_tx: int 
    ) -> bool:
        """
        Update user's Jito tip settings.
        """
        try:
            # Validate inputs
            if reserved_amount < self.MIN_RESERVED_TIP_AMOUNT:
                raise ValueError(f"Reserved amount must be at least {self.MIN_RESERVED_TIP_AMOUNT} SOL")
            
            if tip_per_tx < 10_000: # Minimum 0.000001 SOL per tx
                raise ValueError("Tip per transaction too low")
            
            user.jito_reserved_tip_amount = reserved_amount
            user.jito_tip_per_tx = tip_per_tx
            user.jito_tip_last_updated = datetime.utcnow()
            
            await db.commit()
            logger.info(f"Updated tip settings for {user.wallet_address[:8]}: reserved={reserved_amount} SOL, per_tx={tip_per_tx} lamports")
            return True 
        
        except Exception as e:
            logger.error(f"Failed to update tip settings for {user.wallet_address[:8]}: {e}")
            await db.rollback()
            return False


# Global instance
jito_tip_manager = JitoTipManager()



