# jupiter_referral_program/verify_ultra.py
import asyncio
import httpx
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import settings

async def verify_ultra_setup():
    """Verify Ultra API setup specifically"""
    
    print("🎯 ULTRA API SETUP VERIFICATION")
    print("=" * 60)
    
    # Check config
    required = [
        ("JUPITER_API_KEY", getattr(settings, 'JUPITER_API_KEY', None)),
        ("JUPITER_REFERRAL_ACCOUNT", getattr(settings, 'JUPITER_REFERRAL_ACCOUNT', None)),
    ]
    
    for name, value in required:
        if not value:
            print(f"❌ {name} missing in .env")
            return
        else:
            print(f"✅ {name}: Set")
    
    ref_account = settings.JUPITER_REFERRAL_ACCOUNT
    print(f"\n📋 Using Ultra referral account: {ref_account}")
    
    # Test both BUY and SELL scenarios
    test_cases = [
        {
            "name": "BUY (SOL → Token)",
            "input": "So11111111111111111111111111111111111111112",
            "output": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC for testing
            "amount": "10000000",  # 0.01 SOL
            "expected_fee_in": "USDC"  # Fees in output token for buys
        },
        {
            "name": "SELL (Token → SOL)", 
            "input": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "output": "So11111111111111111111111111111111111111112",
            "amount": "100000",  # 0.1 USDC
            "expected_fee_in": "USDC"  # Fees in input token for sells
        }
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {"x-api-key": settings.JUPITER_API_KEY}
        
        for test in test_cases:
            print(f"\n🧪 {test['name']}")
            print(f"   Expected fee in: {test['expected_fee_in']}")
            
            # Without fee (baseline)
            params_no_fee = {
                "inputMint": test["input"],
                "outputMint": test["output"],
                "amount": test["amount"],
                "slippageBps": "1000"
            }
            
            # With 1% fee
            params_with_fee = params_no_fee.copy()
            params_with_fee["referralAccount"] = ref_account
            params_with_fee["referralFee"] = "100"
            
            try:
                # Get quote without fee
                resp_no_fee = await client.get(
                    "https://api.jup.ag/ultra/v1/order",
                    params=params_no_fee,
                    headers=headers
                )
                
                if resp_no_fee.status_code != 200:
                    print(f"   ❌ Baseline failed: {resp_no_fee.status_code}")
                    continue
                
                data_no_fee = resp_no_fee.json()
                out_no_fee = int(data_no_fee.get("outAmount", 0))
                
                # Get quote with fee
                resp_with_fee = await client.get(
                    "https://api.jup.ag/ultra/v1/order",
                    params=params_with_fee,
                    headers=headers
                )
                
                print(f"   With fee status: {resp_with_fee.status_code}")
                
                if resp_with_fee.status_code == 200:
                    data_with_fee = resp_with_fee.json()
                    out_with_fee = int(data_with_fee.get("outAmount", 0))
                    fee_bps = int(data_with_fee.get("feeBps", 0))
                    
                    print(f"   ✅ Got quote with {fee_bps}bps fee")
                    
                    if fee_bps >= 100:
                        print(f"   🎉 1% FEE IS WORKING!")
                        
                        # Calculate actual percentage
                        if out_no_fee > 0:
                            actual_fee = (1 - (out_with_fee / out_no_fee)) * 100
                            print(f"   Actual fee: {actual_fee:.2f}%")
                            
                        # Check fee mint
                        fee_mint = data_with_fee.get("feeMint", "")
                        if fee_mint:
                            mint_name = "SOL" if "So111" in fee_mint else "USDC" if "EPjFW" in fee_mint else fee_mint[:8]
                            print(f"   Fee collected in: {mint_name}")
                            
                    else:
                        print(f"   ⚠️  Fee mismatch: {fee_bps}bps (expected 100bps)")
                        
                elif resp_with_fee.status_code == 400:
                    error = resp_with_fee.text
                    print(f"   ❌ Error: {error[:200]}")
                    
                    if "referralAccount is initialized" in error:
                        print(f"   🔧 Missing Ultra token account for: {test['expected_fee_in']}")
                        print(f"      Create it at: https://referral.jup.ag/dashboard-ultra")
                        
                else:
                    print(f"   ❌ Unexpected: {resp_with_fee.text[:100]}")
                    
            except Exception as e:
                print(f"   ❌ Test failed: {e}")
    
    print("\n" + "=" * 60)
    print("📋 SUMMARY:")
    print(f"Ultra Referral Account: {ref_account}")
    print("\n🔧 If fees aren't working:")
    print("1. Go to: https://referral.jup.ag/dashboard-ultra")
    print(f"2. Find account: {ref_account}")
    print("3. Create token accounts for SOL, USDC, USDT")
    print("4. Test again")

if __name__ == "__main__":
    asyncio.run(verify_ultra_setup())
    
    