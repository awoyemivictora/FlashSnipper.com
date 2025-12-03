# app/utils/fee_monitor.py
import asyncio
import json
from datetime import datetime, timedelta
import httpx
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from spl.token.instructions import get_associated_token_address
from app.config import settings

async def monitor_fees():
    """Monitor accumulated fees in real-time"""
    
    print("📊 REAL-TIME FEE MONITOR")
    print("=" * 60)
    print(f"Referral Account: {settings.JUPITER_REFERRAL_ACCOUNT}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    connection = AsyncClient(settings.SOLANA_RPC_URL)
    referral_pubkey = Pubkey.from_string(settings.JUPITER_REFERRAL_ACCOUNT)
    
    # Track previous balances to show changes
    previous_balances = {}
    
    while True:
        try:
            print(f"\n🕒 {datetime.now().strftime('%H:%M:%S')}")
            print("-" * 60)
            
            total_value = 0
            
            # Check balances for common tokens
            tokens = [
                ("SOL", settings.SOL_MINT, 9, 100),  # Assume $100 SOL
                ("USDC", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", 6, 1),
                ("USDT", "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB", 6, 1),
            ]
            
            for name, mint, decimals, price in tokens:
                try:
                    mint_pubkey = Pubkey.from_string(mint)
                    ata = get_associated_token_address(referral_pubkey, mint_pubkey)
                    
                    # Get balance
                    balance_info = await connection.get_token_account_balance(ata)
                    
                    if balance_info.value:
                        amount = int(balance_info.value.amount)
                        ui_amount = amount / (10 ** decimals)
                        value_usd = ui_amount * price
                        total_value += value_usd
                        
                        # Check if balance changed
                        previous = previous_balances.get(name, 0)
                        change = ui_amount - previous
                        previous_balances[name] = ui_amount
                        
                        change_symbol = "↑" if change > 0 else "" if change == 0 else "↓"
                        
                        print(f"{name:6} │ {ui_amount:12.6f} {change_symbol}")
                        print(f"        ${value_usd:10.2f}")
                        
                except Exception as e:
                    print(f"{name:6} │ Error: {str(e)[:30]}")
            
            print("-" * 60)
            print(f"TOTAL VALUE: ${total_value:.2f}")
            
            # Check recent trades via API
            async with httpx.AsyncClient(timeout=10.0) as client:
                # You could add API calls here to get recent trades
                pass
            
            # Wait 30 seconds before next update
            await asyncio.sleep(30)
            
        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped")
            break
        except Exception as e:
            print(f"\n⚠️  Error: {e}")
            await asyncio.sleep(10)
    
    await connection.close()

async def get_fee_summary():
    """Get a summary of all accumulated fees"""
    
    print("💰 FEE EARNINGS SUMMARY")
    print("=" * 60)
    
    connection = AsyncClient(settings.SOLANA_RPC_URL)
    referral_pubkey = Pubkey.from_string(settings.JUPITER_REFERRAL_ACCOUNT)
    
    tokens = [
        ("SOL", settings.SOL_MINT, 9, 100),
        ("USDC", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", 6, 1),
        ("USDT", "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB", 6, 1),
    ]
    
    total_value = 0
    
    for name, mint, decimals, price in tokens:
        try:
            mint_pubkey = Pubkey.from_string(mint)
            ata = get_associated_token_address(referral_pubkey, mint_pubkey)
            
            balance_info = await connection.get_token_account_balance(ata)
            
            if balance_info.value:
                amount = int(balance_info.value.amount)
                ui_amount = amount / (10 ** decimals)
                value_usd = ui_amount * price
                total_value += value_usd
                
                print(f"{name:6} │ {ui_amount:12.6f} │ ${value_usd:10.2f}")
            else:
                print(f"{name:6} │ {'0':>12} │ $     0.00")
                
        except Exception as e:
            print(f"{name:6} │ Error: {str(e)[:30]}")
    
    print("-" * 60)
    print(f"TOTAL: ${total_value:.2f}")
    
    await connection.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Fee monitoring")
    parser.add_argument('--monitor', action='store_true', help='Monitor in real-time')
    parser.add_argument('--summary', action='store_true', help='Show summary only')
    
    args = parser.parse_args()
    
    if args.monitor:
        asyncio.run(monitor_fees())
    else:
        asyncio.run(get_fee_summary())
        
        
        
        