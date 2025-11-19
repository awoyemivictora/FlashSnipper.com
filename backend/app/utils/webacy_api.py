import os
import aiohttp
import asyncio
from typing import Dict, List, Optional, Any
from app.utils.bot_logger import get_logger
from app.config import settings

logger = get_logger(__name__)

class WebacyAPI:
    def __init__(self):
        self.base_url = "https://api.webacy.com"
        self.headers = {
            "accept": "application/json",
            "x-api-key": settings.WEBACY_TOKEN
        }
    
    async def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Generic request handler with retry logic and premium endpoint handling"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.base_url}/{endpoint}",
                        headers=self.headers,
                        params=params,
                        timeout=30
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return data
                        elif resp.status == 429:
                            wait_time = 2 ** attempt
                            logger.warning(f"Rate limited, waiting {wait_time}s")
                            await asyncio.sleep(wait_time)
                            continue
                        elif resp.status == 402:
                            logger.error(f"Premium endpoint requires subscription: {endpoint}")
                            return None
                        elif resp.status == 403:
                            logger.error(f"API key invalid or insufficient permissions: {endpoint}")
                            return None
                        else:
                            logger.warning(f"Webacy API error {resp.status} for {endpoint}")
                            return None
            except asyncio.TimeoutError:
                logger.warning(f"Webacy request timeout (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                continue
            except Exception as e:
                logger.error(f"Webacy request failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                continue
        return None

    async def get_threat_risk(self, address: str, chain: str = "sol") -> Optional[Dict]:
        """Get comprehensive threat risk analysis"""
        return await self._make_request(f"addresses/{address}", {"chain": chain})

    async def get_sanction_status(self, address: str, chain: str = "sol") -> Optional[Dict]:
        """Check if address is sanctioned"""
        return await self._make_request(f"addresses/sanctioned/{address}", {"chain": chain})

    async def get_holder_analysis(self, address: str, chain: str = "sol") -> Optional[Dict]:
        """Get detailed holder analysis (premium endpoint)"""
        params = {
            "chain": chain,
            "useCache": "true",
            "refetchData": "false",
            "maxHolders": 10000
        }
        return await self._make_request(f"holder-analysis/{address}", params)

    async def get_token_pools(self, token_address: str, chain: str = "sol") -> Optional[Dict]:
        """Get token pools with risk assessment (premium endpoint)"""
        return await self._make_request(f"tokens/{token_address}/pools", {"chain": chain})

    async def get_token_economics(self, token_address: str, chain: str = "sol", date: str = None) -> Optional[Dict]:
        """Get token economic history (premium endpoint)"""
        params = {"chain": chain}
        if date:
            params["date"] = date  # Fixed parameter name
        return await self._make_request(f"tokens/{token_address}", params)

    async def get_pool_ohlcv(self, pool_address: str, chain: str = "sol", timeframe: str = "minute") -> Optional[Dict]:
        """Get pool OHLCV data with risk assessment (premium endpoint)"""
        params = {
            "chain": chain,
            "timeFrame": timeframe
        }
        return await self._make_request(f"tokens/pools/{pool_address}", params)

# Global instance
webacy_client = WebacyAPI()

async def check_webacy_risk(mint: str) -> Dict:
    """Enhanced risk analysis with comprehensive Webacy data extraction"""
    try:
        # Get comprehensive threat risk
        threat_data = await webacy_client.get_threat_risk(mint)
        if not threat_data:
            return await _get_fallback_risk_data()

        # Extract comprehensive metrics from threat data
        risk_analysis = await _extract_comprehensive_risk_metrics(threat_data, mint)
        
        return risk_analysis
        
    except Exception as e:
        logger.error(f"Enhanced Webacy check failed for {mint}: {e}")
        return await _get_fallback_risk_data()

async def _extract_comprehensive_risk_metrics(threat_data: Dict, mint: str) -> Dict:
    """Extract comprehensive risk metrics from Webacy threat data"""
    
    # Basic risk metrics
    overall_risk = threat_data.get("overallRisk", 100)
    issues = threat_data.get("issues", [])
    details = threat_data.get("details", {})
    
    # Extract key risk factors
    risk_factors = await _extract_risk_factors(issues)
    
    # Extract token information
    token_info = details.get("token_info", {})
    market_data = details.get("marketData", {})
    address_info = details.get("address_info", {})
    
    # Get sanction status
    sanction_data = await webacy_client.get_sanction_status(mint)
    is_sanctioned = sanction_data.get("is_sanctioned", False) if sanction_data else False
    
    # Extract holder concentration
    ownership_dist = market_data.get("ownershipDistribution", {})
    top10_holders_pct = ownership_dist.get("percentageHeldByTop10", 100)
    top5_holders_pct = ownership_dist.get("percentageHeldByTop5", 100)
    
    # Extract liquidity data
    liquidity_data = market_data.get("liquidityData", [])
    total_liquidity = sum(pool.get("totalLiquidity", 0) for pool in liquidity_data) if liquidity_data else 0
    
    # Calculate moon potential with more factors
    moon_potential = await _calculate_enhanced_moon_potential(
        threat_data, mint, token_info, market_data
    )
    
    # Extract deployer risk
    deployer_risk = 0
    deployer_data = threat_data.get("deployer", {})
    if deployer_data:
        deployer_risk_data = deployer_data.get("risk", {})
        deployer_risk = deployer_risk_data.get("overallRisk", 0)
    
    return {
        "risk_score": overall_risk,
        "risk_level": _get_risk_level(overall_risk),
        "moon_potential": moon_potential,
        "confidence": _calculate_confidence(threat_data),
        "issues": issues,
        "risk_factors": risk_factors,
        "sanctioned": is_sanctioned,
        "holder_concentration": {
            "top10_percentage": top10_holders_pct,
            "top5_percentage": top5_holders_pct,
            "concentration_level": _get_concentration_level(top10_holders_pct)
        },
        "liquidity_analysis": {
            "total_liquidity": total_liquidity,
            "pool_count": len(liquidity_data),
            "liquidity_sufficiency": total_liquidity > 10  # 10 SOL threshold
        },
        "token_metadata": {
            "has_socials": bool(token_info.get("twitter") or token_info.get("telegram")),
            "is_metadata_immutable": token_info.get("is_metadata_immutable", False),
            "token_age": _calculate_token_age(address_info.get("time_1st_tx")),
            "transaction_count": address_info.get("transaction_count", 0)
        },
        "deployer_risk": deployer_risk,
        "market_metrics": {
            "volume_24h": market_data.get("total_volume", 0),
            "price_change_24h": market_data.get("price_change_percentage_24h", 0),
            "market_cap": market_data.get("market_cap", 0)
        }
    }

async def _extract_risk_factors(issues: List[Dict]) -> Dict[str, Any]:
    """Extract and categorize risk factors from issues"""
    risk_factors = {
        "high_severity": [],
        "medium_severity": [],
        "low_severity": [],
        "categories": {}
    }
    
    for issue in issues:
        score = issue.get("score", 0)
        tags = issue.get("tags", [])
        categories = issue.get("categories", {})
        
        # Categorize by severity
        if score >= 10:
            severity_list = risk_factors["high_severity"]
        elif score >= 5:
            severity_list = risk_factors["medium_severity"]
        else:
            severity_list = risk_factors["low_severity"]
        
        # Add tags to severity lists
        for tag in tags:
            severity_list.append({
                "name": tag.get("name"),
                "description": tag.get("description"),
                "severity": tag.get("severity", 0)
            })
        
        # Extract categories
        for category_key, category_data in categories.items():
            risk_factors["categories"][category_key] = category_data
    
    return risk_factors

async def _calculate_enhanced_moon_potential(
    threat_data: Dict, 
    mint: str, 
    token_info: Dict, 
    market_data: Dict
) -> float:
    """Calculate enhanced moon potential with more factors"""
    try:
        score = 50  # Base score
        
        # Positive factors
        if token_info.get("twitter"):
            score += 8
        if token_info.get("telegram"):
            score += 7
        if token_info.get("is_metadata_immutable"):
            score += 10
            
        # Liquidity factors
        liquidity_data = market_data.get("liquidityData", [])
        if liquidity_data:
            total_liquidity = sum(pool.get("totalLiquidity", 0) for pool in liquidity_data)
            if total_liquidity > 50:
                score += 15
            elif total_liquidity > 20:
                score += 8
            elif total_liquidity > 10:
                score += 5
        
        # Volume factors
        volume_24h = market_data.get("total_volume", 0)
        if volume_24h > 100000:
            score += 12
        elif volume_24h > 50000:
            score += 8
        elif volume_24h > 10000:
            score += 5
        
        # Holder concentration (negative factor)
        ownership_dist = market_data.get("ownershipDistribution", {})
        top10_percentage = ownership_dist.get("percentageHeldByTop10", 100)
        if top10_percentage > 80:
            score -= 25
        elif top10_percentage > 60:
            score -= 15
        elif top10_percentage > 40:
            score -= 8
            
        # Risk score adjustment
        overall_risk = threat_data.get("overallRisk", 100)
        if overall_risk < 30:
            score += 15
        elif overall_risk < 50:
            score += 8
        elif overall_risk > 80:
            score -= 20
            
        # Get holder analysis for more insights (if available)
        holder_analysis = await webacy_client.get_holder_analysis(mint)
        if holder_analysis:
            first_buyers = holder_analysis.get("first_buyers_analysis", {})
            current_holding = first_buyers.get("current_holding_percentage", 100)
            if current_holding < 30:  # Low holding by first buyers is good
                score += 10
            if first_buyers.get("buyers_still_holding_count", 0) > 10:
                score += 5
                
        return max(0, min(100, score))
        
    except Exception as e:
        logger.error(f"Error calculating enhanced moon potential for {mint}: {e}")
        return 50

def _get_risk_level(score: float) -> str:
    if score <= 30:
        return "low"
    elif score <= 70:
        return "medium"
    else:
        return "high"

def _get_concentration_level(top10_pct: float) -> str:
    if top10_pct > 80:
        return "very_high"
    elif top10_pct > 60:
        return "high"
    elif top10_pct > 40:
        return "moderate"
    else:
        return "low"

def _calculate_token_age(first_tx_time: str) -> Optional[int]:
    """Calculate token age in days"""
    if not first_tx_time:
        return None
    try:
        from datetime import datetime
        first_tx = datetime.fromisoformat(first_tx_time.replace('Z', '+00:00'))
        now = datetime.utcnow()
        age_days = (now - first_tx).days
        return age_days
    except:
        return None

def _calculate_confidence(threat_data: Dict) -> float:
    """Calculate confidence in the risk assessment (0-100)"""
    try:
        details = threat_data.get("details", {})
        address_info = details.get("address_info", {})
        
        confidence = 50
        
        # Increase confidence based on data completeness
        if address_info.get("transaction_count", 0) > 10:
            confidence += 20
        if address_info.get("time_1st_tx"):
            confidence += 15
        if details.get("token_info"):
            confidence += 15
        if details.get("marketData", {}).get("liquidityData"):
            confidence += 10
            
        return min(100, confidence)
    except:
        return 50

async def _get_fallback_risk_data() -> Dict:
    """Return fallback risk data when API fails"""
    return {
        "risk_score": 100,
        "risk_level": "high",
        "moon_potential": 0,
        "confidence": 0,
        "issues": [],
        "risk_factors": {
            "high_severity": [],
            "medium_severity": [],
            "low_severity": [],
            "categories": {}
        },
        "sanctioned": False,
        "holder_concentration": {
            "top10_percentage": 100,
            "top5_percentage": 100,
            "concentration_level": "very_high"
        },
        "liquidity_analysis": {
            "total_liquidity": 0,
            "pool_count": 0,
            "liquidity_sufficiency": False
        },
        "token_metadata": {
            "has_socials": False,
            "is_metadata_immutable": False,
            "token_age": None,
            "transaction_count": 0
        },
        "deployer_risk": 100,
        "market_metrics": {
            "volume_24h": 0,
            "price_change_24h": 0,
            "market_cap": 0
        }
    }
    
    
    