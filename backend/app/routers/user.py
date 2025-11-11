from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import logging
from app.database import get_db
from app.models import User, Snipe, Trade
from app.security import get_current_user
from app.schemas import UserBotSettingsResponse, UserBotSettingsUpdate, UserProfile, SnipeLog, TradeLog


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/user",
    tags=['User']
)



# ---- User Profile Endpoint ----
@router.get("/me", response_model=UserProfile)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Retrieves the authenticated user's profile.
    """
    return UserProfile(
        wallet_address=current_user.wallet_address,
        is_active=current_user.is_active,
        is_premium=current_user.is_premium
    )
    

# ----- User Snipes (Logs) Endpoint ----
@router.get("/me/snipes", response_model=List[SnipeLog])
async def get_my_snipes(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Retrieves all snipe records for the authenticated user.
    """
    try:
        result = await db.execute(
            select(Snipe)
            .filter(Snipe.user_wallet_address == current_user.wallet_address)
            .order_by(Snipe.started_at.desc())
        )
        snipes = result.scalars().all()
        return [SnipeLog.from_orm(snipe) for snipe in snipes]
    except Exception as e:
        logger.error(f"Error fetching snipes for user {current_user.wallet_address}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching user snipes")
    


#---- User Trade History Endpoint -----
@router.get("/me/trades", response_model=List[TradeLog])
async def get_my_trades(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Retrieves all trade records for the authenticated user.
    """
    try:
        result = await db.execute(
            select(Trade)
            .filter(Trade.user_wallet_address == current_user.wallet_address)
            .order_by(Trade.timestamp.desc())
        )
        trades = result.scalars().all()
        return [TradeLog.from_orm(trade) for trade in trades]
    except Exception as e:
        logger.error(f"Error fetching trades for user {current_user.wallet_address}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching user trade history")
    
    

@router.get("/active-trades", response_model=List[TradeLog]) # Assuming TradeLog schema matches needed data
async def get_active_trades(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Retrieves active trade positions for the current user for frontend monitoring.
    """
    # You might need a specific field in your Trade model to indicate 'active' or 'open' status
    # Or query `TokenMetadata` table if it tracks active holdings.
    # For this example, let's assume Trade records can indicate a position is open
    # e.g., if it's a 'buy' trade and no corresponding 'sell' trade has been logged for it yet.
    # A more robust solution might involve a dedicated `UserPosition` table.

    # For simplicity, let's assume you fetch all trades and frontend filters or
    # you query a specific status.
    # If your `Trade` table has `is_open: bool` flag:
    # result = await db.execute(select(Trade).filter_by(user_wallet_address=current_user.wallet_address, is_open=True))
    # Or based on your `token_metadata` table:
    # For now, let's return all trades logged and assume frontend processes it
    # based on `trade_type` and other fields.
    result = await db.execute(select(Trade).filter(Trade.user_wallet_address == current_user.wallet_address).order_by(Trade.timestamp.desc()))
    trades = result.scalars().all()
    # Filter for active positions if your `Trade` model supports it (e.g., `is_sold` flag within `Trade` model)
    active_trades = [
        TradeLog.from_orm(trade) for trade in trades
        if trade.trade_type == "buy" and (trade.profit_usd is None or trade.profit_usd == 0) # Simplified check for 'open'
    ]
    return active_trades

    
    




# Endpoint to GET a user's bot settings
@router.get("/settings/{wallet_address}", response_model=UserBotSettingsResponse)
async def get_user_settings(
    wallet_address: str,
    current_user: User = Depends(get_current_user), # Ensures user is authenticated
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves the bot configuration and filter preferences for the authenticated user.
    """
    # Security check: Ensure the authenticated user is requesting their own settings
    if current_user.wallet_address != wallet_address:
        logger.warning(f"Unauthorized attempt to access settings: User {current_user.wallet_address} tried to access {wallet_address}'s settings.")
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to view these settings."
        )

    user_data = await db.get(User, wallet_address) # Fetch user directly by primary key

    if not user_data:
        logger.error(f"User not found for wallet address: {wallet_address}")
        raise HTTPException(
            status_code=404,
            detail="User not found."
        )

    # Return the user data, Pydantic will handle the mapping to UserBotSettingsResponse
    return user_data




# Endpoint to PUT (update) a user's bot settings
@router.put("/settings/{wallet_address}", response_model=UserBotSettingsResponse)
async def update_user_settings(
    wallet_address: str,
    settings: UserBotSettingsUpdate, # Request body with updated settings
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates the bot configuration and filter preferences for the authenticated user.
    """
    # Security check: Ensure the authenticated user is updating their own settings
    if current_user.wallet_address != wallet_address:
        logger.warning(f"Unauthorized attempt to update settings: User {current_user.wallet_address} tried to update {wallet_address}'s settings.")
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to update these settings."
        )

    user_to_update = await db.get(User, wallet_address)

    if not user_to_update:
        logger.error(f"User not found for wallet address: {wallet_address}")
        raise HTTPException(
            status_code=404,
            detail="User not found."
        )

    # Update user fields from the incoming settings
    # Iterate over the Pydantic model's fields and update the ORM object
    # Exclude 'is_premium' from direct update if it's managed by subscription logic
    # Make sure to handle nullable fields (e.g., filter_top_holders_max_pct) correctly
    for field, value in settings.model_dump(exclude_unset=True).items(): # `exclude_unset=True` is useful for PATCH, for PUT all fields are usually sent
        # Only update fields that are not `is_premium` if it's managed separately
        if field == "is_premium":
            continue # Do not allow direct update of premium status via this endpoint
        setattr(user_to_update, field, value)

    # Special handling for boolean filters: ensure they are boolean, not None if passed as such
    # Pydantic usually handles this, but it's good to be explicit
    user_to_update.filter_socials_added = settings.filter_socials_added
    # ... repeat for all boolean filter fields if needed ...
    # user_to_update.filter_liquidity_burnt = settings.filter_liquidity_burnt

    try:
        db.add(user_to_update) # Add to session if not already tracked
        await db.commit()
        await db.refresh(user_to_update) # Refresh to load any changes from DB (e.g., updated_at)
        logger.info(f"User settings updated successfully for {wallet_address}")
        return user_to_update # Return the updated user object
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update user settings for {wallet_address}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update settings: {str(e)}"
        )



