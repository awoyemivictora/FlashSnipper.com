import os
import aiohttp
import json
from typing import Dict, List, Optional
from app.utils.bot_logger import get_logger
from app.config import settings

logger = get_logger(__name__)

class TavilyAPI:
    def __init__(self):
        self.api_key = settings.TAVILY_API_KEY
        self.base_url = "https://api.tavily.com"
    
    async def search_news(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search for news and market sentiment about a token"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "include_answer": True,
                    "include_images": False,
                    "include_raw_content": False,
                    "max_results": max_results
                }
                
                async with session.post(
                    f"{self.base_url}/search",
                    json=payload,
                    timeout=30
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("results", [])
                    else:
                        logger.error(f"Tavily API error: {resp.status}")
                        return []
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return []
    
    async def analyze_sentiment(self, token_name: str, token_symbol: str) -> Dict:
        """Analyze market sentiment for a token"""
        queries = [
            f"{token_name} {token_symbol} crypto news latest",
            f"{token_name} {token_symbol} token analysis",
            f"{token_name} {token_symbol} solana meme coin",
            f"{token_name} {token_symbol} market sentiment today",
            f"{token_name} {token_symbol} exchange listing rumor",
            f"{token_name} {token_symbol} trading volume spike",
            f"{token_name} {token_symbol} partnership announcement",
            f"{token_name} {token_symbol} rugpull warning OR scam OR exploit",
        ]
        
        all_articles = []
        for query in queries:
            articles = await self.search_news(query, 5)
            all_articles.extend(articles)
        
        return self._calculate_sentiment(all_articles, token_symbol)
    
    def _calculate_sentiment(self, articles: List[Dict], token_symbol: str) -> Dict:
        """Calculate sentiment score from articles"""
        if not articles:
            return {"score": 50, "sentiment": "neutral", "confidence": 0, "article_count": 0}
        
        positive_keywords = ["bullish", "moon", "pump", "growth", "partnership", "listing", "adoption"]
        negative_keywords = ["scam", "rugpull", "dump", "warning", "fake", "fraud", "exploit"]
        
        positive_count = 0
        negative_count = 0
        total_articles = len(articles)
        
        for article in articles:
            content = f"{article.get('title', '')} {article.get('content', '')}".lower()
            
            # Check for positive signals
            if any(keyword in content for keyword in positive_keywords):
                positive_count += 1
            
            # Check for negative signals
            if any(keyword in content for keyword in negative_keywords):
                negative_count += 1
        
        # Calculate sentiment score (0-100)
        if total_articles > 0:
            positive_ratio = positive_count / total_articles
            negative_ratio = negative_count / total_articles
            sentiment_score = 50 + (positive_ratio * 25) - (negative_ratio * 25)
        else:
            sentiment_score = 50
        
        sentiment_score = max(0, min(100, sentiment_score))
        
        # Determine sentiment label
        if sentiment_score >= 70:
            sentiment = "bullish"
        elif sentiment_score >= 60:
            sentiment = "slightly_bullish"
        elif sentiment_score >= 40:
            sentiment = "neutral"
        elif sentiment_score >= 30:
            sentiment = "slightly_bearish"
        else:
            sentiment = "bearish"
        
        confidence = min(100, total_articles * 10)  # More articles = more confidence
        
        return {
            "score": sentiment_score,
            "sentiment": sentiment,
            "confidence": confidence,
            "article_count": total_articles,
            "positive_articles": positive_count,
            "negative_articles": negative_count
        }

# Global instance
tavily_client = TavilyAPI()


