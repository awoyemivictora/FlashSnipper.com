from fastapi import APIRouter, Depends
from app.dependencies import get_current_user_by_wallet
from app.models import User
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/util",
    tags=['Util']
)


@router.get("/dashboard_info")
async def get_dashboard_info(
    current_user: User = Depends(get_current_user_by_wallet)
):
    """
    Provides general dashboard information relevant to the current user.
    """
    info = {
        "wallet_address": current_user.wallet_address,
        "is_premium": current_user.is_premium,
        "email": current_user.email,
        # TODO: Add aggregated snipe statistics, recent analysis summaries etc.
        "recent_snipes_count": 0, # Fetch from DB
        "active_snipes_count": 0, # Fetch from DB/in-memory
    }
    logger.info(f"Dashboard info requested for {current_user.wallet_address}")
    return info



