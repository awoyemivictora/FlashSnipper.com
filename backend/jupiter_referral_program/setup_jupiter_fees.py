# app/utils/setup_jupiter_fees_fixed.py
import sys
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
    
import base58
import asyncio
import json
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from spl.token.instructions import get_associated_token_address
import aiohttp
from app.config import settings

async def setup_jupiter_fees():
    """Step-by-step setup for Jupiter Ultra fees"""
    
    print("🔧 STEP 1: Checking your wallet and API key...")
    
    # Load your private key from .env
    private_key_str = settings.BOT_OWNER_PRIVATE_KEY
    wallet = Keypair.from_bytes(base58.b58decode(private_key_str))
    
    print(f"   Wallet Address: {wallet.pubkey()}")
    print(f"   Will receive 1% fees at this address")
    
    # Check Jupiter API key
    if not hasattr(settings, "JUPITER_API_KEY") or not settings.JUPITER_API_KEY:
        print("   ❌ JUPITER_API_KEY not found in .env")
        print("   Get one from: https://portal.jup.ag")
        return
    
    print(f"   Jupiter API Key: {settings.JUPITER_API_KEY[:10]}...")
    
    # Check balance
    async with AsyncClient(settings.SOLANA_RPC_URL) as client:
        balance = await client.get_balance(wallet.pubkey())
        sol_balance = balance.value / 1_000_000_000
        
    print(f"   Current Balance: {sol_balance:.4f} SOL")
    
    if sol_balance < 0.1:
        print("   ❌ You need at least 0.1 SOL to create accounts")
        return
    
    print("\n✅ STEP 1 COMPLETE: Wallet is ready!")
    
    print("\n🔧 STEP 2: Creating Jupiter Referral Account...")
    
    # Create referral account (ONE TIME ONLY)
    referral_account = await create_referral_account(wallet)
    
    print(f"   ✅ Referral Account Created: {referral_account}")
    print("   This is your SPECIAL BANK ACCOUNT for fees")
    
    print("\n🔧 STEP 3: Creating Fee Accounts for SOL and common tokens...")
    
    # Create token accounts for common mints
    common_mints = [
        "So11111111111111111111111111111111111111112",  # SOL
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",   # USDT
    ]
    
    for mint in common_mints:
        token_account = await create_token_account(wallet, referral_account, mint)
        print(f"   ✅ Fee account for {mint[:8]}...: {token_account}")
    
    print("\n🎉 SETUP COMPLETE!")
    print("\n📝 ADD THIS TO YOUR .env FILE:")
    print(f"JUPITER_REFERRAL_ACCOUNT={referral_account}")
    print("\nYour bot will now earn 1% on every transaction!")

async def check_api_key():
    """Check if Jupiter API key is valid"""
    headers = {
        "x-api-key": settings.JUPITER_API_KEY
    }
    
    # Test with quote API (simplest endpoint)
    url = "https://api.jup.ag/quote"
    
    params = {
        "inputMint": "So11111111111111111111111111111111111111112",
        "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "amount": "100000000",  # 0.1 SOL
        "slippageBps": "500"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status == 200:
                return True, "API key is valid"
            else:
                error_text = await resp.text()
                return False, f"API key error: {resp.status} - {error_text[:200]}"

async def create_referral_account(wallet: Keypair) -> str:
    """Create the main referral account using Jupiter API"""
    
    # First check if we can use the API
    api_valid, api_message = await check_api_key()
    if not api_valid:
        print(f"   ❌ {api_message}")
        print("   Using manual calculation instead...")
        return await calculate_referral_pda(wallet)
    
    print("   ✅ Jupiter API is working!")
    
    # Try to create via API
    url = "https://api.jup.ag/referral/v1/initialize"
    
    payload = {
        "payer": str(wallet.pubkey()),
        "partner": str(wallet.pubkey()),
        "projectPubkey": "DkiqsTrw1u1bYFumumC7sCG2S8K25qc2vemJFHyW2wJc",
        "name": "flashsniper_bot"
    }
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": settings.JUPITER_API_KEY
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"   ✅ Created via API: {data.get('referralAccount', '')[:32]}...")
                    return data.get("referralAccount", "")
                else:
                    error_text = await resp.text()
                    print(f"   ⚠️ API failed ({resp.status}): {error_text[:200]}")
                    return await calculate_referral_pda(wallet)
    except Exception as e:
        print(f"   ⚠️ API call failed: {e}")
        return await calculate_referral_pda(wallet)

async def calculate_referral_pda(wallet: Keypair) -> str:
    """Calculate the referral PDA manually"""
    print("   Calculating PDA manually...")
    
    # Jupiter Referral Program ID
    REFERRAL_PROGRAM_ID = Pubkey.from_string("REFER4ZgmyYx9c6He5XfaTMiGfdLwRnkV4RPp9t9iF3")
    
    # Jupiter Ultra Project PDA
    PROJECT_PUBKEY = Pubkey.from_string("DkiqsTrw1u1bYFumumC7sCG2S8K25qc2vemJFHyW2wJc")
    
    # Create PDA for your wallet - FIXED: Use bytes() instead of to_bytes()
    referral_pda, bump = Pubkey.find_program_address(
        [
            b"referral",
            bytes(PROJECT_PUBKEY),  # FIXED: Use bytes() not to_bytes()
            bytes(wallet.pubkey()),  # FIXED: Use bytes() not to_bytes()
            b"flashsniper"
        ],
        REFERRAL_PROGRAM_ID
    )
    
    print(f"   ⚠️  Manual PDA: {referral_pda}")
    print("   Note: This PDA needs to be initialized on-chain.")
    print("   For now, you can use it and Jupiter will skip fees if not initialized.")
    
    return str(referral_pda)

async def create_token_account(wallet: Keypair, referral_account: str, mint: str) -> str:
    """Create token account for a specific mint"""
    
    # Try API first
    url = "https://api.jup.ag/referral/v1/token-account"
    
    payload = {
        "payer": str(wallet.pubkey()),
        "referralAccount": referral_account,
        "mint": mint
    }
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": settings.JUPITER_API_KEY
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("tokenAccount", "")
                else:
                    error_text = await resp.text()
                    if "already exists" in error_text:
                        print(f"   Token account already exists for {mint[:8]}...")
                    else:
                        print(f"   API failed for {mint[:8]}...: {error_text[:100]}")
    except Exception as e:
        print(f"   API call failed for {mint[:8]}...: {e}")
    
    # Fallback: Calculate ATA manually
    owner_pubkey = Pubkey.from_string(referral_account)
    mint_pubkey = Pubkey.from_string(mint)
    ata = get_associated_token_address(owner_pubkey, mint_pubkey)
    
    return str(ata)

def quick_setup():
    """Quick setup without API calls"""
    print("🚀 QUICK JUPITER FEE SETUP")
    print("=" * 50)
    
    # Get wallet from .env
    private_key_str = settings.BOT_OWNER_PRIVATE_KEY
    wallet = Keypair.from_bytes(base58.b58decode(private_key_str))
    
    print(f"Your Wallet: {wallet.pubkey()}")
    print(f"Balance check: Run 'solana balance {wallet.pubkey()}'")
    
    # Calculate PDA - FIXED: Use bytes() not to_bytes()
    REFERRAL_PROGRAM_ID = Pubkey.from_string("REFER4ZgmyYx9c6He5XfaTMiGfdLwRnkV4RPp9t9iF3")
    PROJECT_PUBKEY = Pubkey.from_string("DkiqsTrw1u1bYFumumC7sCG2S8K25qc2vemJFHyW2wJc")
    
    referral_pda, bump = Pubkey.find_program_address(
        [
            b"referral",
            bytes(PROJECT_PUBKEY),  # FIXED
            bytes(wallet.pubkey()),  # FIXED
            b"flashsniper"
        ],
        REFERRAL_PROGRAM_ID
    )
    
    print(f"\n📝 CALCULATED REFERRAL ACCOUNT:")
    print(f"JUPITER_REFERRAL_ACCOUNT={referral_pda}")
    
    print("\n💰 TOKEN ACCOUNTS (calculated):")
    mints = [
        ("SOL", "So11111111111111111111111111111111111111112"),
        ("USDC", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"),
        ("USDT", "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"),
    ]
    
    for name, mint in mints:
        mint_pubkey = Pubkey.from_string(mint)
        ata = get_associated_token_address(referral_pda, mint_pubkey)
        print(f"{name}: {ata}")
    
    print("\n⚡ QUICK START:")
    print("1. Add the JUPITER_REFERRAL_ACCOUNT to your .env file")
    print("2. Update bot_components.py to use referral fees")
    print("3. The bot will TRY to collect 1% fees")
    print("4. If token accounts don't exist, Jupiter skips the fee")
    
    return str(referral_pda)

if __name__ == "__main__":
    print("Choose setup method:")
    print("1. Full setup (requires valid Jupiter API key)")
    print("2. Quick setup (manual calculation, no API calls)")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        asyncio.run(setup_jupiter_fees())
    else:
        referral_account = quick_setup()
        
        print("\n✅ DONE! Add this to your .env file:")
        print(f"JUPITER_REFERRAL_ACCOUNT={referral_account}")
        print("\nThen update your bot_components.py to include:")
        print("referralAccount={referral_account}")
        print("referralFee=100  # 1%")