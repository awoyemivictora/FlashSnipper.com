# app/dependencies.py
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User
from sqlalchemy.future import select

# Remove this import to break circular dependency
# from app.utils.bot_logger import get_logger

# Create a simple logger here instead
import logging
logger = logging.getLogger(__name__)

# If you decide to add email/password login later
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token")

async def get_current_user_by_wallet(
    wallet_address: str = Header(..., alias="wallet-address"),
    db: AsyncSession = Depends(get_db)
) -> User:
    result = await db.execute(
        select(User).where(User.wallet_address == wallet_address)
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(wallet_address=wallet_address)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"New user auto-created: {wallet_address}")

    return user

async def get_premium_user(current_user: User = Depends(get_current_user_by_wallet)):
    if not current_user.is_premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium subscription required for this feature."
        )
    return current_user

