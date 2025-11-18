from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.models import AIAnalysis, User
from app.schemas import AIAnalysisRequest, AIAnalysisResponse
from app.utils.bot_logger import get_logger
from app.dependencies import get_current_user_by_wallet, get_premium_user # Import get_premium_user
from datetime import datetime, timedelta

logger = get_logger(__name__)

router = APIRouter(
    prefix="/sentiment",
    tags=['Sentiment']
)


# @router.post("/analyze", response_model=AIAnalysisResponse)
# async def analyze_token(
#     analysis_request: AIAnalysisRequest,
#     current_user: User = Depends(get_current_user_by_wallet),
#     db: AsyncSession = Depends(get_db)
# ):
#     """
#     Analyzes a token's sentiment, performs basic rug checks, and saves the analysis.
#     Premium users get access to more detailed rug checks.
#     """
#     token_address = analysis_request.token_address
    
#     # Check for recent analysis in DB to avoid redundant API calls
#     # Cache for 1 hour for non-premium, maybe less for premium
#     cache_duration = timedelta(hours=1) if not current_user.is_premium else timedelta(minutes=10)

#     result = await db.execute(
#         select(AIAnalysis)
#         .where(AIAnalysis.token_address == token_address)
#         .where(AIAnalysis.analyzed_at >= (datetime.now() - cache_duration))
#         .order_by(AIAnalysis.analyzed_at.desc())
#     )
#     cached_analysis = result.scalar_one_or_none()

#     if cached_analysis and not current_user.is_premium:
#         logger.info(f"Returning cached basic analysis for {token_address}")
#         return cached_analysis
#     elif cached_analysis and current_user.is_premium and (datetime.now() - cached_analysis.analyzed_at < timedelta(minutes=5)):
#          # Premium users get fresher data, but still cache for very short period
#          logger.info(f"Returning cached premium analysis for {token_address} (fresh).")
#          return cached_analysis
    
#     logger.info(f"Performing new analysis for token: {token_address}")

#     # --- Perform Sentiment Analysis ---
#     sentiment_data = await get_token_sentiment_and_analysis(token_address)
#     sentiment_score = sentiment_data.get("sentiment_score")
#     openai_summary = sentiment_data.get("openai_analysis_summary")

#     # --- Perform Rug Check ---
#     rug_check_data = await perform_rug_check(token_address)
#     rug_check_result_str = rug_check_data.get("result", "unknown") # e.g., "safe", "danger"
    
#     # Map rugcheck.xyz result to a simpler status
#     if "danger" in rug_check_result_str.lower() or "rugged" in rug_check_result_str.lower():
#         overall_rug_status = "high_risk"
#     elif "warning" in rug_check_result_str.lower() or "suspicious" in rug_check_result_str.lower():
#         overall_rug_status = "medium_risk"
#     else:
#         overall_rug_status = "safe"

#     # --- Premium Features for Rug Check (only if user is premium) ---
#     lp_locked = None
#     mint_authority_revoked = None
#     top_10_holders_percentage = None
#     token_bundled_percentage = None
#     token_same_block_buys = None

#     if current_user.is_premium:
#         logger.info(f"Performing premium rug checks for {token_address} for premium user.")
#         lp_locked = await check_lp_locked(token_address)
#         mint_authority_revoked = await check_mint_authority_revoked(token_address)
#         top_10_holders_percentage = await check_top_10_holders_percentage(token_address)
#         token_bundled_percentage = await check_token_bundled_percentage(token_address)
#         token_same_block_buys = await check_token_same_block_buys(token_address)
        
#         # Combine rugcheck.xyz with custom checks to refine overall_rug_status
#         # (This logic would be more detailed based on your risk model)
#         if lp_locked is False or top_10_holders_percentage and top_10_holders_percentage > 70:
#             overall_rug_status = "high_risk"
#         elif lp_locked is None and "unknown" in overall_rug_status:
#             overall_rug_status = "medium_risk" # More cautious if LP status is unknown for premium

#     new_analysis = AIAnalysis(
#         token_address=token_address,
#         sentiment_score=sentiment_score,
#         openai_analysis_summary=openai_summary,
#         rug_check_result=overall_rug_status,
#         rug_check_details=rug_check_data, # Store raw data
#         top_10_holders_percentage=top_10_holders_percentage,
#         lp_locked=lp_locked,
#         mint_authority_revoked=mint_authority_revoked,
#         # Save other premium checks if you implement them fully
#     )
#     db.add(new_analysis)
#     await db.commit()
#     await db.refresh(new_analysis)
    
#     logger.info(f"Analysis for {token_address} saved.")
#     return new_analysis



# @router.get("/analyze/{token_address}", response_model=AIAnalysisResponse)
# async def get_token_analysis(
#     token_address: str,
#     current_user: User = Depends(get_current_user_by_wallet),
#     db: AsyncSession = Depends(get_db)
# ):
#     """
#     Retrieves the latest analysis for a token.
#     Triggers a new analysis if no recent data is found.
#     """
#     # Simply call the POST endpoint for consistency or re-use logic
#     analysis_request = AIAnalysisRequest(token_address=token_address)
#     return await analyze_token(analysis_request, current_user, db)



