from cryptography.fernet import Fernet
import os
from datetime import datetime, timedelta
from jose import JWTError, jwt
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from app.database import get_db
from app.models import User
from app.utils.bot_logger import get_logger

logger = get_logger(__name__)

# Backend's Master AES Key (loaded from environment variable)
BACKEND_AES_MASTER_KEY = os.getenv("BACKEND_AES_MASTER_KEY")
if not BACKEND_AES_MASTER_KEY:
    raise ValueError("BACKEND_AES_MASTER_KEY environment variable not set.")
backend_cipher_suite = Fernet(BACKEND_AES_MASTER_KEY.encode())

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-jwt-key")
JWT_ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60

ACCESS_TOKEN_EXPIRE_MINUTES=43200   # 30 days
# or 10080 for 7 days

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# FIXED: Now returns STRING (base64-url-safe) — DB expects str!
def encrypt_private_key_backend(private_key_bytes: bytes) -> str:
    """Encrypts raw private key bytes using backend's master key and returns base64 string."""
    logger.info("Encrypting private key with backend master key")
    encrypted_bytes = backend_cipher_suite.encrypt(private_key_bytes)
    return encrypted_bytes.decode('utf-8')  # ← THIS WAS THE MISSING LINE

# FIXED: Accepts string from DB, converts to bytes first
# def decrypt_private_key_backend(encrypted_private_key_str: str) -> bytes:
#     """Decrypts private key from base64 string stored in DB."""
#     logger.info("Decrypting private key with backend master key")
#     encrypted_bytes = encrypted_private_key_str.encode('utf-8')  # ← convert back to bytes
#     return backend_cipher_suite.decrypt(encrypted_bytes)

def decrypt_private_key_backend(encrypted_private_key_data) -> bytes:
    """Decrypts private key - handles both str and bytes input."""
    logger.info("Decrypting private key with backend master key")
    
    # Handle both string and bytes input
    if isinstance(encrypted_private_key_data, bytes):
        encrypted_bytes = encrypted_private_key_data
    else:
        # It's a string, convert to bytes
        encrypted_bytes = encrypted_private_key_data.encode('utf-8')
    
    return backend_cipher_suite.decrypt(encrypted_bytes)


async def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    # logger.info(f"Created JWT for wallet: {data.get('sub')}")
    return encoded_jwt

# async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     try:
#         payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
#         wallet_address: str = payload.get("sub")
#         if not wallet_address:
#             raise credentials_exception
#     except JWTError as e:
#         logger.error(f"JWT decode error: {str(e)}")
#         raise credentials_exception

#     result = await db.execute(select(User).filter(User.wallet_address == wallet_address))
#     user = result.scalar_one_or_none()
#     if not user:
#         logger.error(f"User not found for wallet: {wallet_address}")
#         raise credentials_exception
#     return user







async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        wallet_address: str = payload.get("sub")
        exp = payload.get("exp")

        if not wallet_address:
            raise credentials_exception

        # If token is expired or expires in < 5 minutes → we'll refresh it below
        if exp and datetime.fromtimestamp(exp) < datetime.utcnow() + timedelta(minutes=5):
            raise JWTError("Token expired or expiring soon")

    except JWTError as e:
        logger.warning(f"JWT invalid or expired: {str(e)} - Forcing re-authentication")
        
        # INSTEAD OF RAISING 401 — RETURN A CLEAR MESSAGE + 401
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="TOKEN_EXPIRED",  # ← This is the key!
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # User lookup
    result = await db.execute(select(User).filter(User.wallet_address == wallet_address))
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exception

    # OPTIONAL: Attach fresh token to response (so frontend can update)
    # This is the PRO move
    fresh_token = await create_access_token({"sub": user.wallet_address})
    # You can access this in endpoints via request.state.user = user, request.state.token = fresh_token

    return user




