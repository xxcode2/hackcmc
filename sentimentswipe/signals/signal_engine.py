"""
SENTIMENTSWIPE V2 - Signal Engine
Fetches and processes sentiment data from CMC API
"""

import requests
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from config.config import (
    CMC_API_KEY, WEIGHT_FEAR_GREED, WEIGHT_SOCIAL, WEIGHT_FUNDING,
    SIGNAL_HISTORY_WINDOW
)

logger = logging.getLogger(__name__)

class SignalEngine:
    """Fetches and calculates sentiment signals from CMC"""
    
    BASE_URL = "https://pro-api.coinmarketcap.com"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.signal_history: List[Dict] = []
        self.last_fetch = None
        
    def _headers(self) -> Dict:
        return {
            "X-CMC_PRO_API_KEY": self.api_key,
            "Accept": "application/json"
        }
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make API request with retry logic"""
        url = f"{self.BASE_URL}{endpoint}"
        for attempt in range(3):
            try:
                resp = requests.get(url, headers=self._headers(), params=params, timeout=10)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    logger.warning("Rate limited, waiting 60s...")
                    time.sleep(60)
                else:
                    logger.error(f"API error {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.error(f"Request failed: {e}")
                time.sleep(5)
        return None
    
    def get_fear_greed(self) -> Tuple[float, float]:
        """
        Get Fear & Greed index
        Returns: (value 0-100, timestamp)
        """
        # CMC uses indicator ID 57 for Fear & Greed
        data = self._make_request("/v3/indicator/57", {"limit": 1})
        if data and "data" in data and data["data"]:
            point = data["data"][0]
            value = float(point.get("value", 50))
            timestamp = point.get("timestamp", datetime.now().isoformat())
            return value, timestamp
        return 50.0, datetime.now().isoformat()
    
    def get_social_sentiment(self, symbols: List[str] = None) -> Tuple[float, float]:
        """
        Get social sentiment score from social posts
        Returns: (score -1 to +1, confidence 0 to 1)
        """
        if symbols is None:
            symbols = ["BTC", "ETH", "BNB"]
        
        # Get recent social posts via CMC
        total_sentiment = 0.0
        count = 0
        
        for symbol in symbols[:5]:  # Top 5 for efficiency
            data = self._make_request("/v2/social/posts", {
                "symbol": symbol,
                "limit": 50
            })
            if data and "data" in data:
                posts = data["data"].get(symbol, [])
                for post in posts:
                    # Simple sentiment based on platforms + engagement
                    engagement = post.get("engagement_score", 0)
                    platforms = post.get("platforms", [])
                    # More platforms = higher reach = higher weight
                    platform_count = len(platforms) if isinstance(platforms, list) else 1
                    total_sentiment += (engagement * platform_count)
                    count += 1
        
        if count == 0:
            return 0.0, 0.0
        
        # Normalize to -1 to +1
        raw_sentiment = total_sentiment / count
        normalized = (raw_sentiment - 50) / 50  # Assume raw is 0-100
        normalized = max(-1.0, min(1.0, normalized))
        
        confidence = min(1.0, count / 50)  # More data = higher confidence
        
        return normalized, confidence
    
    def get_funding_rates(self, symbols: List[str] = None) -> Tuple[float, float]:
        """
        Get funding rates for perpetual futures
        Returns: (average funding rate, sentiment: positive=bullish, negative=bearish)
        """
        if symbols is None:
            symbols = ["BTC", "ETH", "BNB"]
        
        rates = []
        for symbol in symbols:
            # Try funding rate endpoint
            data = self._make_request(f"/v2/futures/{symbol}/funding_rate")
            if data and "data" in data:
                funding = data["data"].get("funding_rate", 0)
                if funding is not None:
                    rates.append(float(funding))
        
        if not rates:
            return 0.0, 0.0
        
        avg_rate = sum(rates) / len(rates)
        
        # Scale to -50 to +50 (funding typically -0.1% to +0.1%)
        scaled = avg_rate * 500  # 0.1% → 50
        
        return avg_rate, scaled
    
    def get_price_momentum(self, symbols: List[str] = None) -> float:
        """
        Calculate price momentum (1h change)
        Returns: momentum score -100 to +100
        """
        if symbols is None:
            symbols = ["BTC", "ETH", "BNB"]
        
        momentum = 0.0
        count = 0
        
        for symbol in symbols:
            data = self._make_request("/v2/quotes/latest", {
                "symbol": symbol,
                "convert": "USD"
            })
            if data and "data" in data:
                quote = data["data"].get(symbol, {}).get("quote", {}).get("USD", {})
                change_1h = quote.get("percent_change_1h", 0)
                change_24h = quote.get("percent_change_24h", 0)
                
                # Weight: recent momentum more important
                score = (change_1h * 2 + change_24h) / 3
                momentum += score
                count += 1
        
        if count == 0:
            return 0.0
        
        # Normalize: typical crypto change is -10% to +10%
        # Cap at ±50
        normalized = max(-50, min(50, momentum / count * 5))
        return normalized
    
    def calculate_composite_signal(self) -> Dict:
        """
        Calculate the composite sentiment signal
        Returns dict with all components and final score
        """
        # Fetch all signals
        fg_value, fg_timestamp = self.get_fear_greed()
        social_score, social_confidence = self.get_social_sentiment()
        funding_rate, funding_sentiment = self.get_funding_rates()
        momentum = self.get_price_momentum()
        
        # Normalize Fear & Greed: 0-100 → -50 to +50
        fg_normalized = fg_value - 50
        
        # Apply weights
        raw_score = (
            fg_normalized * WEIGHT_FEAR_GREED +
            social_score * social_confidence * 50 * WEIGHT_SOCIAL +
            funding_sentiment * WEIGHT_FUNDING
        )
        
        # Apply momentum filter
        prev_signal = self.signal_history[-1]["composite"] if self.signal_history else 0
        momentum_delta = raw_score - prev_signal
        
        if abs(momentum_delta) > 30:
            # Sudden reversal - reduce confidence
            raw_score = prev_signal + (momentum_delta * 0.5)
        
        # Clamp to -100 to +100
        composite = max(-100, min(100, raw_score))
        
        # Determine action based on signal
        if composite > 40:
            action = "TAKE_PROFIT"
        elif composite > 20:
            action = "SLIGHT_BULLISH"
        elif composite < -40:
            action = "BUY_DIP"
        elif composite < -20:
            action = "ACCUMULATE"
        else:
            action = "NEUTRAL"
        
        signal_data = {
            "timestamp": datetime.now().isoformat(),
            "fear_greed": fg_value,
            "social_sentiment": social_score,
            "social_confidence": social_confidence,
            "funding_rate": funding_rate,
            "funding_sentiment": funding_sentiment,
            "momentum": momentum,
            "composite": composite,
            "action": action,
            "prev_composite": prev_signal,
            "momentum_delta": momentum_delta
        }
        
        # Store in history
        self.signal_history.append(signal_data)
        if len(self.signal_history) > SIGNAL_HISTORY_WINDOW * 12:  # 5min cycles
            self.signal_history.pop(0)
        
        self.last_fetch = datetime.now()
        
        return signal_data
    
    def get_signal_summary(self) -> str:
        """Get human-readable signal summary"""
        sig = self.calculate_composite_signal()
        return f"""
╔══════════════════════════════════════════╗
║         SENTIMENTSWIPE SIGNAL            ║
╠══════════════════════════════════════════╣
║ Fear & Greed: {sig['fear_greed']:.1f}/100               ║
║ Social: {sig['social_sentiment']:+.2f} ({sig['social_confidence']:.0%} conf)        ║
║ Funding Rate: {sig['funding_rate']:.4f}%              ║
║ Momentum: {sig['momentum']:+.1f}                    ║
╠══════════════════════════════════════════╣
║ COMPOSITE: {sig['composite']:+.1f}                       ║
║ ACTION: {sig['action']}               ║
╚══════════════════════════════════════════╝
"""