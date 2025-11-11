import base64
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.schemas import TokenResponse, WalletRegisterRequest
from app.security import create_access_token, encrypt_private_key_backend
from app.models import User
from app.schemas import UserCreate, UserResponse
from app.utils.logger import get_logger
from cryptography.fernet import Fernet
# from app.utils.security import verify_password, get_password_hash, create_access_token # You'd need a security.py

logger = get_logger(__name__)


router = APIRouter(
    prefix="/auth",
    tags=['Auth']
)



# --- Frontend Encryption Key Provision (Temporary, for browser-side encryption) ---
# Generate a new Fernet key for each session or on request for frontend encryption.
# This key is only for encrypting the private key ONCE for transfer to backend.
# The backend's master key (BACKEND_AES_MASTER_KEY) is different and used for storage.

@router.get("/get-frontend-encryption-key")
async def get_frontend_encryption_key():
    """
    Provides a temporary AES key for the frontend to encrypt the wallet's private key
    before sending it to the backend. This key is meant for one-time use or per-session.
    """
    # Generate a new Fernet key (which uses AES-GCM under the hood)
    # The key itself is Base64URL encoded.
    temp_key = Fernet.generate_key().decode('utf-8')
    logger.info("Generated new temporary frontend encryption key.")
    return {"key": temp_key}



#----- User Registration / Login Endpoint ---
@router.post("/register-or-login", response_model=TokenResponse)
async def register_or_login_wallet(request: WalletRegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Registers a new user wallet or logs in an existing one,
    storing the private key securely on the backend using AES.
    """
    wallet_address = request.wallet_address
    # This is the Base64-encoded bundle (ciphertext + IV + tag)
    encrypted_private_key_bundle_b64 = request.encrypted_private_key_bundle

    # The backend itself does NOT need to decrypt this bundle with the frontend's
    # *temporary* AES key. The frontend sends the *raw private key bytes* (after client-side generation)
    # to the backend *already encrypted by the backend's master key*.

    # IMPORTANT: The previous logic assumed frontend sent XOR-encrypted JSON string.
    # The new secure flow is:
    # Frontend: Generates Keypair -> Gets raw bytes -> Calls backend for *backend's* temporary AES key -> Encrypts raw bytes with *that* key -> Sends encrypted bundle to backend.
    # Backend: Receives encrypted bundle -> Stores it.
    # The backend decrypts only when needed for transactions using its *master* AES key.

    # This means the frontend needs to handle the encryption with the temporary key
    # before sending it to the backend.
    # For now, let's assume the frontend sends the *raw private key bytes*,
    # and the backend *directly encrypts it with its own master key* for storage.
    # This is slightly less ideal than frontend doing AES with a temporary key,
    # but simpler to implement initially if the "raw private key bytes" are just Base64 encoded.

    # Let's clarify the `request.encrypted_private_key_bundle` expectation:
    # Assuming frontend sends the raw private key (Uint8Array) directly Base64-encoded.
    # This means the frontend has *not* applied any encryption, just encoding.
    try:
        # Decode the Base64 string into raw private key bytes
        raw_private_key_bytes = base64.b64decode(encrypted_private_key_bundle_b64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Base64 format for private key: {e}")

    # Now, encrypt these raw bytes using the backend's strong AES master key
    backend_encrypted_pk = encrypt_private_key_backend(raw_private_key_bytes)

    # Check if user already exists
    result = await db.execute(select(User).filter_by(wallet_address=wallet_address))
    user = result.scalar_one_or_none()

    if user:
        user.encrypted_private_key = backend_encrypted_pk
        await db.commit()
        await db.refresh(user)
        logger.info(f"User {wallet_address} logged in and private key updated (AES encrypted).")
    else:
        user = User(
            wallet_address=wallet_address,
            encrypted_private_key=backend_encrypted_pk
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"New user {wallet_address} registered (AES encrypted).")

    access_token = await create_access_token(data={"sub": user.wallet_address})
    return TokenResponse(access_token=access_token, token_type="bearer", wallet_address=user.wallet_address)


