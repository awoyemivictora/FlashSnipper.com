import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/solsniper_db")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your_super_secret_jwt_key") # Change this in production!
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    SOLANA_RPC_URL: str = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    SOLANA_WEBSOCKET_URL: str = os.getenv("SOLANA_WEBSOCKET_URL", "wss://api.mainnet-beta.solana.com/")

    DEXSCREENER_API_URL: str = os.getenv("DEXSCREENER_API_URL", "https://api.dexscreener.com/latest/dex/tokens/")
    RUGCHECK_API_URL: str = os.getenv("RUGCHECK_API_URL", "https://api.rugcheck.xyz/v1/tokens/") # Confirm actual endpoint
    
    TWITTER_BEARER_TOKEN: str = os.getenv("TWITTER_BEARER_TOKEN") # For Twitter API v2
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    
    STRIPE_PREMIUM_PRICE_ID = os.getenv("STRIPE_PREMIUM_PRICE_ID", "price_xxx")

    # STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY")
    # STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET")
    # PAYSTACK_SECRET_KEY: str = os.getenv("PAYSTACK_SECRET_KEY")
    # PAYSTACK_PUBLIC_KEY: str = os.getenv("PAYSTACK_PUBLIC_KEY")

    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "a_very_strong_32_byte_key_for_aes_encryption!") # 32-byte key for AES256

settings = Settings()