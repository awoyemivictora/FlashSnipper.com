# app/utils/fee_manager.py
import logging
from typing import Dict, Any
from app.models import User
from app.utils.fee_tracker import FeeTracker

logger = logging.getLogger(__name__)

class UnifiedFeeManager:
    """Unified fee calculation and decision making"""
    
    # Constants
    SMALL_TRADE_THRESHOLD_SOL = 0.1
    MIN_PROFITABLE_TRADE_SOL = 0.01
    
    def __init__(self, redis_client):
        """Initialize with Redis client"""
        self.tracker = FeeTracker(redis_client)
    
    async def calculate_fee_decision(
        self,
        user: User,
        trade_type: str,
        amount_sol: float,
        mint: str,
        pnl_pct: float = 0.0
    ) -> Dict[str, Any]:
        """
        Calculate unified fee decision.
        Returns dict with: should_apply, fee_bps, referral_fee, reason
        """
        
        # 1. Check if trade is too small to be profitable
        if amount_sol < self.MIN_PROFITABLE_TRADE_SOL:
            return {
                "should_apply": False,
                "fee_bps": 0,
                "referral_fee": "0",
                "reason": "trade_too_small",
                "details": f"Trade {amount_sol:.4f} SOL < {self.MIN_PROFITABLE_TRADE_SOL:.2f} SOL"
            }
        
        # 2. Check small trade threshold
        if amount_sol < self.SMALL_TRADE_THRESHOLD_SOL:
            return {
                "should_apply": False,
                "fee_bps": 0,
                "referral_fee": "0",
                "reason": "small_trade",
                "details": f"Trade {amount_sol:.4f} SOL < {self.SMALL_TRADE_THRESHOLD_SOL:.2f} SOL"
            }
        
        # 3. Don't apply fees to losing stop losses
        if pnl_pct < -5.0 and trade_type in ["STOP_LOSS", "TRAILING_STOP"]:
            return {
                "should_apply": False,
                "fee_bps": 0,
                "referral_fee": "0",
                "reason": "losing_stop_loss",
                "details": f"Stop loss at {pnl_pct:.1f}% loss"
            }
        
        # 4. Use the tracker for the actual decision
        should_apply = await self.tracker.should_apply_fee(
            user_wallet=user.wallet_address,
            trade_type=trade_type,
            amount_sol=amount_sol,
            mint=mint,
            pnl_pct=pnl_pct
        )
        
        if not should_apply:
            return {
                "should_apply": False,
                "fee_bps": 0,
                "referral_fee": "0",
                "reason": "fee_optimizer_waived",
                "details": "FeeOptimizer waived fee"
            }
        
        # 5. Calculate optimal fee
        fee_bps = await self.tracker.calculate_optimal_fee_bps(
            user_wallet=user.wallet_address,
            amount_sol=amount_sol,
            trade_type=trade_type,
            is_premium=user.is_premium
        )
        
        if fee_bps <= 0:
            return {
                "should_apply": False,
                "fee_bps": 0,
                "referral_fee": "0",
                "reason": "zero_fee_calculated",
                "details": f"FeeOptimizer returned {fee_bps}bps"
            }
        
        return {
            "should_apply": True,
            "fee_bps": fee_bps,
            "referral_fee": str(fee_bps),
            "reason": "applied",
            "details": f"Applying {fee_bps}bps ({fee_bps/100:.1f}%) fee"
        }
    
    @staticmethod
    def get_fee_decision_key(user_wallet: str, mint: str, trade_type: str = "") -> str:
        """Get consistent Redis key for fee decisions"""
        if trade_type:
            return f"fee:{user_wallet}:{mint}:{trade_type}"
        return f"fee:{user_wallet}:{mint}"
    
    async def track_trade_for_fee_optimization(
        self,
        user_wallet: str,
        amount_sol: float,
        mint: str,
        trade_type: str 
    ):
        """Track trade metrics for future fee optimization"""
        await self.tracker.track_trade_for_fee_optimization(
            user_wallet=user_wallet,
            amount_sol=amount_sol,
            mint=mint,
            trade_type=trade_type
        )
        
        
        
        
        
        