# app/utils/fee_tracker.py
import logging
import redis.asyncio as redis
from typing import Optional

logger = logging.getLogger(__name__)

# Redis client (you can import your existing redis_client or create a new one)
# If you already have redis_client in bot_components.py, you can pass it as parameter
# or create a new connection

class FeeTracker:
    """Track trade metrics for fee optimization - NO circular dependencies"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def track_trade_for_fee_optimization(
        self,
        user_wallet: str,
        amount_sol: float,
        mint: str,
        trade_type: str 
    ):
        """Track trade metrics for future fee optimization"""
        
        # Track 24h trade count
        await self.redis.incr(f"trade_count_24h:{user_wallet}")
        await self.redis.expire(f"trade_count_24h:{user_wallet}", 86400)
        
        # Track 30d volume
        volume_key = f"volume_30d:{user_wallet}"
        current_volume = await self.redis.get(volume_key) or "0"
        new_volume = float(current_volume) + amount_sol
        await self.redis.set(volume_key, str(new_volume))
        await self.redis.expire(volume_key, 2592000)  # 30 days
        
        # Track total trades
        await self.redis.incr(f"total_trades:{user_wallet}")
        
        # Track token-specific trading
        token_trades_key = f"token_trades:{user_wallet}:{mint}"
        await self.redis.incr(token_trades_key)
        await self.redis.expire(token_trades_key, 604800) # 7 days
    
    async def should_apply_fee(
        self,
        user_wallet: str,
        trade_type: str,
        amount_sol: float,
        mint: str,
        pnl_pct: float = 0.0
    ) -> bool:
        """
        Determine if we should apply referral fee based on multiple factors.
        Returns True if fee should be applied.
        """
        
        # 1. NEVER apply fees on losing trades
        if pnl_pct < -5.0 and trade_type in ["SELL", "STOP_LOSS", "TIMEOUT"]:
            logger.info(f"💰 Fee waived: Trade at {pnl_pct:.1f}% loss")
            return False 
        
        # 2. Small trade threshold
        SMALL_TRADE_THRESHOLD = 0.1 # SOL
        if amount_sol < SMALL_TRADE_THRESHOLD:
            logger.info(f"💰 Fee waived: Small trade ({amount_sol:.4f} SOL)")
            return False 
        
        # 3. High-frequency trader discount
        user_trades_24h = await self.redis.get(f"trade_count_24h:{user_wallet}")
        if user_trades_24h and int(user_trades_24h) > 10:
            # High-frequency traders get 50% fee discount
            logger.info(f"💰 Reduced fee: High-frequency trader ({user_trades_24h} trades/24h)")
            return True # Still apply fee, but at reduced rate
        
        # 4. VIP/Whale discount
        total_volume_30d = await self.redis.get(f"volume_30d:{user_wallet}")
        if total_volume_30d and float(total_volume_30d) > 100:  # 100 SOL volume
            logger.info(f"💰 Reduced fee: High-volume trader ({float(total_volume_30d):.1f} SOL/30d))")
            return True # Apply at reduced rate
        
        # 5. New user grace period (first 3 trades fee)
        user_trade_count = await self.redis.get(f"total_trades:{user_wallet}")
        if not user_trade_count or int(user_trade_count) < 3:
            logger.info(f"💰 Fee waived: New user grace period (trade {int(user_trade_count or 0) + 1}/3)")
            return False 
        
        # 6. Default: Apply fee for profitable, medium+ sized trades
        return True
    
    async def calculate_optimal_fee_bps(
        self,
        user_wallet: str,
        amount_sol: float,
        trade_type: str,
        is_premium: bool = False
    ) -> int:
        """
        Calculate optimal fee in basis points.
        Lower fees for better user experience, higher for profitability.
        """
        
        base_fee = 100  # 1% default
        
        # Premium users get 50% discount
        if is_premium:
            base_fee = 50   # 0.5%
            
        # Volume-based discounts
        volume_30d = await self.redis.get(f"volume_30d:{user_wallet}")
        if volume_30d:
            volume = float(volume_30d)
            if volume > 500:    # 500 SOL volume
                base_fee = max(25, base_fee // 2)   # At most 50% discount
            elif volume > 100:  # 100 SOL volume
                base_fee = max(50, base_fee * 2 // 3)   # 33% discount
        
        # Trade size based adjustment
        if amount_sol > 1.0:    # Large trades get slight discount
            base_fee = max(50, base_fee - 10)
        
        # Don't apply fees to stop losses
        if "STOP_LOSS" in trade_type or "TIMEOUT" in trade_type:
            return 0
        
        return base_fee
    
    
    
    
    