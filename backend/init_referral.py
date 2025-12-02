# init_referral_FINAL.py
import asyncio
import base58
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.message import MessageV0
from solders.transaction import VersionedTransaction
from solana.rpc.async_api import AsyncClient
from spl.token.instructions import create_associated_token_account, get_associated_token_address
from solana.rpc.types import TxOpts # <-- ADD THIS IMPORT
from app.config import settings

# Option B – base58 string (easiest if you have it)
YOUR_WALLET_PRIVATE_KEY = "2mxPb8rKtiEmDrEyWFF7hLppa9qchG67uDV6AjT2Ca48fZfbDNsVf4sfzG52apzkiinKo437C9dFzC2CYYkoth8e"
REFERRAL_PDA = "6aXqJy4sHcyexqPjKVLuroTCRd4JTgQDmBKHZ3jUnuBU"
WSOL_MINT = "So11111111111111111111111111111111111111112"
RPC_URL = settings.SOLANA_RPC_URL

async def main():
    # Auto-detect format and load keypair
    if isinstance(YOUR_WALLET_PRIVATE_KEY, str):
        kp = Keypair.from_bytes(base58.b58decode(YOUR_WALLET_PRIVATE_KEY))
    else:
        kp = Keypair.from_bytes(bytes(YOUR_WALLET_PRIVATE_KEY))
    
    print(f"Your wallet: {kp.pubkey()}")

    client = AsyncClient(RPC_URL)

    ata = get_associated_token_address(
        owner=Pubkey.from_string(REFERRAL_PDA),
        mint=Pubkey.from_string(WSOL_MINT)
    )
    print(f"Referral WSOL ATA: {ata}")

    info = await client.get_account_info(ata)
    if info.value:
        print("ATA ALREADY EXISTS → You are ready to earn 1% fees!")
        await client.close()
        return

    print("Creating referral ATA for Wrapped SOL...")
    ix = create_associated_token_account(
        payer=kp.pubkey(),
        owner=Pubkey.from_string(REFERRAL_PDA),
        mint=Pubkey.from_string(WSOL_MINT)
    )

    bh = (await client.get_latest_blockhash()).value.blockhash
    msg = MessageV0.try_compile(kp.pubkey(), [ix], [], bh)
    tx = VersionedTransaction(msg, [kp])

    # FIX IS HERE: Use TxOpts instead of a dictionary
    sig = await client.send_transaction(
        tx, 
        opts=TxOpts(skip_preflight=True, max_retries=3)
    )
    print(f"Transaction: https://solscan.io/tx/{sig.value}")
    
    await client.confirm_transaction(sig.value)
    print("Referral ATA created! Your bot will now earn 1% on every trade")

    await client.close()

if __name__ == "__main__":
    asyncio.run(main())