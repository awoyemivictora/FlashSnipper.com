# from fastapi import APIRouter, Depends, HTTPException
# from app.dependencies import get_current_admin_user
# from app.utils.bot_components import get_fee_statistics
# from app.config import settings
# from sqlalchemy.ext.asyncio import AsyncSession

# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.ext.asyncio import AsyncSession
# from app.database import get_db
# from app.utils.bot_components import get_fee_analytics

# router = APIRouter(prefix="/admin", tags=["Admin"])




# # In your admin commands or API endpoints
# async def admin_check_fees():
#     """Admin command to check fee status"""
#     print("📊 BOT FEE COLLECTION STATUS")
#     print("=" * 60)
    
#     # Check settings
#     ref_account = getattr(settings, 'JUPITER_REFERRAL_ACCOUNT', None)
#     if not ref_account:
#         print("❌ JUPITER_REFERRAL_ACCOUNT not set in .env")
#         return
    
#     print(f"✅ Ultra Referral Account: {ref_account}")
#     print(f"   Dashboard: https://referral.jup.ag/dashboard-ultra")
    
#     # Get fee summary
#     summary = await get_bot_fee_summary()
    
#     print(f"\n📈 Fee Collection Statistics:")
#     print(f"   Total fee transactions: {summary.get('total_fee_transactions', 0)}")
#     print(f"   Recent fee count: {summary.get('recent_fee_count', 0)}")
    
#     if 'total_fee_amount' in summary and summary['total_fee_amount'] > 0:
#         print(f"   Total fee amount: {summary['total_fee_amount']}")
    
#     print(f"\n🔗 Check your fee balance:")
#     print(f"   1. Go to: https://referral.jup.ag/dashboard-ultra")
#     print(f"   2. Connect your wallet")
#     print(f"   3. Find account: {ref_account}")
#     print(f"   4. Click to see accumulated fees")
    
#     print(f"\n💡 Remember: Ultra takes 20% of your 1% fee")
#     print(f"   You receive 80% of the 1% fee")
    
    
    
# @router.get("/admin/fee-analytics")
# async def fee_analytics(
#     db: AsyncSession = Depends(get_db),
#     current_user: dict = Depends(get_current_admin_user)
# ):
#     """Get fee analytics (admin only)"""
#     try:
#         analytics = await get_fee_analytics(db)
#         return {
#             "success": True,
#             "data": analytics,
#             "ultra_referral_account": settings.JUPITER_REFERRAL_ACCOUNT
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


