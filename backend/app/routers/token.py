from fastapi import Depends, APIRouter
import os
from dotenv import load_dotenv
import logging
from app.models import User
from app.security import get_current_user
from app.utils.dexscreener_api import get_dexscreener_data
from app.utils.raydium_apis import get_raydium_pool_info
from app.utils.solscan_apis import get_solscan_token_meta
from app.utils.token_safety import check_token_safety


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load your environment variables and API keys.
load_dotenv()

router = APIRouter(
    prefix="/token",
    tags=['Token']
)


# Endpoint to get safety report for a mint_address
@router.get("/safety-check/{mint_address}")
async def get_token_safety_report(mint_address: str, current_user: User = Depends(get_current_user)):
    """Endpoint to get full safety report for a token"""
    return await check_token_safety(mint_address)



# Endpoint to get the token metadata for a mint_address from DEXSCREENER
@router.get("/metadata/{mint_address}")
async def get_token_metadata(mint_address: str, current_user: User = Depends(get_current_user)):
    """Combined token metadaa from all dexscreener api"""
    dex_data = await get_dexscreener_data(mint_address)
    
    return {
        "dex_data": dex_data
    }


# Endpoint to get the token metadata for a mint_address from SOLSCAN
@router.get("/metadata/{mint_address}")
async def get_token_metadata(mint_address: str, current_user: User = Depends(get_current_user)):
    """Combined token metadaa from solscan api"""
    solscan_data = await get_solscan_token_meta(mint_address)
    
    return {
        "solscan_data": solscan_data,
    }


# Endpoint to get the token metadata for a mint_address from RAYDIUM
@router.get("/metadata/{mint_address}")
async def get_token_metadata(mint_address: str, current_user: User = Depends(get_current_user)):
    """Combined token metadaa from raydium"""
    raydium_data = await get_raydium_pool_info(mint_address)
    
    return {
        "raydium_data": raydium_data,
    }


# Endpoint to get the token metadata for a mint_address from ALL ENDPOINTS (DEXSCREENER, SOLSCAN & RAYDIUM)
@router.get("/metadata/{mint_address}")
async def get_token_metadata(mint_address: str, current_user: User = Depends(get_current_user)):
    """Combined token metadaa from all sources"""
    dex_data = await get_dexscreener_data(mint_address)
    raydium_data = await get_raydium_pool_info(mint_address)
    solscan_data = await get_solscan_token_meta(mint_address)
    
    
    return {
        "dex_data": dex_data,
        "raydium_data": raydium_data,
        "solscan_data": solscan_data,
        "safety_report": await check_token_safety(mint_address)
    }



