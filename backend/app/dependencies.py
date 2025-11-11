from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User
from app.utils.logger import get_logger
from sqlalchemy.future import select

logger = get_logger(__name__)

# If you decide to add email/password login later
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token")

async def get_current_user_by_wallet(
    wallet_address: str, 
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Retrieves the user based on the wallet address provided in a header or query param.
    For this simplified scenario, we're assuming the wallet address is always known
    from the frontend's auto-generated wallet.
    """
    if not wallet_address:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wallet address header is missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    result = await db.execute(select(User).where(User.wallet_address == wallet_address))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User (wallet) not found."
        )
    return user

async def get_premium_user(current_user: User = Depends(get_current_user_by_wallet)):
    if not current_user.is_premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium subscription required for this feature."
        )
    return current_user



