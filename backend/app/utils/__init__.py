from .redis_client import get_redis_client
from .fee_manager import UnifiedFeeManager
from .fee_tracker import FeeTracker

# Create shared instances
redis_client = get_redis_client()
fee_manager = UnifiedFeeManager(redis_client)

__all__ = ['redis_client', 'fee_manager', 'UnifiedFeeManager', 'FeeTracker', 'get_redis_client']

