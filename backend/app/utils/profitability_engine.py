# app/profitability_engine.py
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class TokenAnalysis:
    mint: str
    risk_score: float
    moon_potential: float
    sentiment_score: float
    holder_concentration: float
    liquidity_score: float
    social_score: float
    technical_score: float
    final_score: float
    confidence: float
    recommendation: str
    reasons: List[str]

class ProfitabilityEngine:
    def __init__(self):
        self.weights = {
            'risk': -0.50,
            'moon_potential': 0.35,
            'liquidity': 0.25,
            'holder_distribution': -0.30,
            'socials': 0.10,
            'technical': 0.15,
        }

        self.THRESHOLDS = {
            'MAX_RISK': 32,
            'MIN_MOON': 82,
            'MAX_HOLDER_CONCENTRATION': 48,
            'MIN_LIQUIDITY_SCORE': 88,
            'MIN_CONFIDENCE': 78,
            'MIN_FINAL_SCORE_MOONBAG': 88,
        }

    async def analyze_token(self, mint: str, token_data: Dict, webacy_data: Dict,
                          raydium_data: Dict) -> TokenAnalysis:

        risk_score = webacy_data.get("risk_score", 100)
        moon_potential = webacy_data.get("moon_potential", 0)
        holder_concentration = webacy_data.get("holder_concentration", 100)
        holder_score = max(0, 100 - holder_concentration)

        liquidity_score = self._calculate_liquidity_score(raydium_data, token_data)
        social_score = self._calculate_social_score(token_data)
        technical_score = self._calculate_technical_score(token_data)

        final_score = (
            self.weights['risk'] * max(0, 100 - risk_score) +
            self.weights['moon_potential'] * moon_potential +
            self.weights['holder_distribution'] * holder_score +
            self.weights['liquidity'] * liquidity_score +
            self.weights['socials'] * social_score +
            self.weights['technical'] * technical_score
        )
        final_score = max(0, min(100, 50 + final_score))

        recommendation, reasons = self._generate_recommendation(
            final_score, risk_score, moon_potential, holder_concentration,
            liquidity_score, webacy_data
        )

        confidence = self._calculate_confidence(webacy_data, liquidity_score, token_data)

        return TokenAnalysis(
            mint=mint,
            risk_score=risk_score,
            moon_potential=moon_potential,
            sentiment_score=0,
            holder_concentration=holder_concentration,
            liquidity_score=liquidity_score,
            social_score=social_score,
            technical_score=technical_score,
            final_score=final_score,
            confidence=confidence,
            recommendation=recommendation,
            reasons=reasons
        )

    def _calculate_liquidity_score(self, raydium_data: Dict, token_data: Dict) -> float:
        score = 0
        if not raydium_data or not raydium_data.get("data"): return 0
        pool = raydium_data["data"][0]
        if pool.get("burnPercent", 0) != 100: return 0
        tvl = pool.get("tvl", 0)
        vol_24h = token_data.get("volume_h24", 0)
        if tvl >= 30000: score += 50
        elif tvl >= 15000: score += 35
        elif tvl >= 8000: score += 20
        if vol_24h > 150000: score += 40
        elif vol_24h > 70000: score += 25
        return min(100, score)

    def _calculate_social_score(self, token_data: Dict) -> float:
        score = 50
        if token_data.get("socials_present"): score += 50
        return min(100, score)

    def _calculate_technical_score(self, token_data: Dict) -> float:
        score = 60
        if token_data.get("price_change_m5", 0) > 15: score += 30
        if token_data.get("volume_m5", 0) > 50000: score += 10
        return min(100, score)

    def _calculate_confidence(self, webacy_data: Dict, liquidity_score: float, token_data: Dict) -> float:
        conf = 70
        if webacy_data.get("confidence", 0) > 85: conf += 20
        if liquidity_score >= 90: conf += 15
        if token_data.get("volume_h24", 0) > 100000: conf += 10
        return min(100, conf)

    def _generate_recommendation(self, final_score, risk_score, moon_potential,
                               holder_concentration, liquidity_score, webacy_data):
        reasons = []
        if risk_score > 60: reasons.append("High risk")
        if holder_concentration > 60: reasons.append("Dev/sniper hold")
        if liquidity_score < 80: reasons.append("LP not safe")

        if (risk_score <= self.THRESHOLDS['MAX_RISK'] and
            moon_potential >= self.THRESHOLDS['MIN_MOON'] and
            holder_concentration <= self.THRESHOLDS['MAX_HOLDER_CONCENTRATION'] and
            liquidity_score >= self.THRESHOLDS['MIN_LIQUIDITY_SCORE'] and
            final_score >= self.THRESHOLDS['MIN_FINAL_SCORE_MOONBAG'] and
            not webacy_data.get("is_honeypot") and
            not webacy_data.get("has_mint_authority") and
            not webacy_data.get("has_freeze")):
            return "MOONBAG_BUY", ["ULTRA SAFE MOONBAG"]

        if final_score >= 78: return "STRONG_BUY", reasons or ["Strong signals"]
        if final_score >= 68: return "BUY", reasons or ["Good setup"]
        return "SKIP", reasons or ["Does not meet criteria"]

profitability_engine = ProfitabilityEngine()

