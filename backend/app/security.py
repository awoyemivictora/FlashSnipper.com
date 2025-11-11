# app/security.py (Create or update this file)
from cryptography.fernet import Fernet
import os
import base64
from datetime import datetime, timedelta
from jose import JWTError, jwt
from typing import Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from app.database import get_db
from app.models import User


# --- Backend's Master AES Key (for encrypting/decrypting user private keys at rest) ---
# GENERATE THIS ONCE AND STORE IN YOUR .env: Fernet.generate_key().decode()
BACKEND_AES_MASTER_KEY = os.getenv("BACKEND_AES_MASTER_KEY")
if not BACKEND_AES_MASTER_KEY:
    raise ValueError("BACKEND_AES_MASTER_KEY environment variable not set.")
backend_cipher_suite = Fernet(BACKEND_AES_MASTER_KEY.encode())



def encrypt_private_key_backend(private_key_bytes: bytes) -> bytes:
    """Encrypts raw private key bytes using backend's master key."""
    return backend_cipher_suite.encrypt(private_key_bytes)



def decrypt_private_key_backend(encrypted_private_key_bytes: bytes) -> bytes:
    """Decrypts raw private key bytes using backend's master key."""
    return backend_cipher_suite.decrypt(encrypted_private_key_bytes)



# --- JWT Secret Key ---
# This is separate from the AES key and used for JWTs.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-jwt-key")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60 # Long-lived token if no other auth method

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        wallet_address: str = payload.get("sub")
        if wallet_address is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).filter(User.wallet_address == wallet_address))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user

