# claim_fees.py
import asyncio
import base58
import aiohttp
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from app.config import settings

async def claim_fees():
    """Claim all accumulated 1% fees"""
    
    print("💰 CLAIMING YOUR 1% FEES")
    print("=" * 50)
    
    # Load your wallet
    private_key_str = settings.BOT_OWNER_PRIVATE_KEY
    wallet = Keypair.from_bytes(base58.b58decode(private_key_str))
    referral_account = settings.JUPITER_REFERRAL_ACCOUNT
    
    print(f"Wallet: {wallet.pubkey()}")
    print(f"Referral Account: {referral_account}")
    
    # Claim fees
    url = "https://api.jup.ag/referral/v1/claim-all"
    
    payload = {
        "payer": str(wallet.pubkey()),
        "referralAccount": referral_account
    }
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": settings.JUPITER_API_KEY
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                
                print(f"\n✅ FEES CLAIMED!")
                print(f"Transactions to sign: {len(data['transactions'])}")
                
                # You would sign and send these transactions
                # For now, just show them
                for i, tx_data in enumerate(data['transactions']):
                    print(f"\nTransaction {i+1}:")
                    print(f"  Mint: {tx_data.get('mint', 'Unknown')}")
                    print(f"  Amount: {tx_data.get('amount', 0)}")
                    
            else:
                error = await resp.text()
                print(f"❌ Failed to claim fees: {error}")

if __name__ == "__main__":
    asyncio.run(claim_fees())
    
    
    