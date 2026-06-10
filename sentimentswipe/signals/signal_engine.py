"""
SENTIMENTSWIPE V2 - Signal Engine
Fetches and processes sentiment data from CMC API v1
"""

import requests
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class SignalEngine:
    """Fetches and calculates sentiment signals from CMC v1 API"""
    
    BASE_URL = "https://pro-api.coinmarketcap.com"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.signal_history: List[Dict] = []
        self.last_fetch = None
        self._prev_market_cap = None
    
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
                    logger.error(f"API error {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                logger.error(f"Request failed: {e}")
                time.sleep(5)
        return None
    
    def get_global_metrics(self) -> Optional[Dict]:
        """Get global market metrics (substitute for Fear & Greed)"""
        data = self._make_request("/v1/global-metrics/quotes/latest")
        if data and "data" in data:
            return data["data"]
        return None
    
    def get_fear_greed_proxy(self) -> Tuple[float, str]:
        """
        Derive Fear & Greed proxy from market data:
        - Market cap change 24h → sentiment
        - BTC dominance change → risk appetite
        - Altcoin volume ratio → market mood
        
        Returns: (value 0-100, timestamp)
        """
        metrics = self.get_global_metrics()
        if not metrics:
            return 50.0, datetime.now().isoformat()
        
        quote = metrics.get("quote", {}).get("USD", {})
        
        # Primary signal: 24h market cap change
        mcap_change = quote.get("total_market_cap_yesterday_percentage_change", 0)
        btc_dom = metrics.get("btc_dominance", 50)
        btc_dom_change = metrics.get("btc_dominance_24h_percentage_change", 0)
        
        # Volume ratio: stablecoin vs altcoin volume
        stable_vol = quote.get("stablecoin_volume_24h", 0)
        alt_vol = quote.get("altcoin_volume_24h", 0)
        vol_ratio = alt_vol / stable_vol if stable_vol > 0 else 1.0
        
        # Calculate Fear & Greed proxy (0-100)
        # Based on: mcap_change (major) + btc_dom trend + volume ratio
        fg_value = 50.0  # neutral baseline
        
        # Market cap change: typical range -10% to +10%
        # Map to -30 to +30 FG contribution
        fg_value += (mcap_change / 10.0) * 30
        
        # BTC dominance: high dominance = fear/risk-off (bearish alt season)
        # Normal range 40-65%, map to -15 to +15
        btc_dom_norm = (btc_dom - 52) / 10 * 15
        fg_value -= btc_dom_norm
        
        # Volume ratio: high altcoin volume = greed/risk-on
        # Normal range 0.5-2.0, map to -10 to +10
        vol_contribution = (vol_ratio - 1.0) * 10
        fg_value += vol_contribution
        
        # Clamp to 0-100
        fg_value = max(0, min(100, fg_value))
        
        timestamp = metrics.get("last_updated", datetime.now().isoformat())
        
        return fg_value, timestamp
    
    def get_price_data(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get price + change data for symbols"""
        sym_str = ",".join(symbols)
        data = self._make_request(
            "/v1/cryptocurrency/quotes/latest",
            {"symbol": sym_str}
        )
        if data and "data" in data:
            return data["data"]
        return {}
    
    def get_sentiment_from_momentum(self, symbols: List[str] = None) -> Tuple[float, float]:
        """
        Calculate sentiment from price momentum across major tokens.
        Returns: (sentiment -1 to +1, confidence 0 to 1)
        """
        if symbols is None:
            symbols = ["BTC", "ETH", "BNB"]
        
        price_data = self.get_price_data(symbols)
        
        total_score = 0.0
        count = 0
        
        for symbol in symbols:
            if symbol not in price_data:
                continue
            
            quote = price_data[symbol].get("quote", {}).get("USD", {})
            if not quote:
                continue
            
            # Combine 1h, 24h, 7d momentum
            chg_1h = quote.get("percent_change_1h", 0) or 0
            chg_24h = quote.get("percent_change_24h", 0) or 0
            chg_7d = quote.get("percent_change_7d", 0) or 0
            
            # Weighted momentum: recent matters more
            momentum = (chg_1h * 3 + chg_24h * 2 + chg_7d) / 6
            
            # Normalize: typical crypto is -10% to +10% daily
            # Scale to -1 to +1
            normalized = max(-1.0, min(1.0, momentum / 10.0))
            
            total_score += normalized
            count += 1
        
        if count == 0:
            return 0.0, 0.0
        
        sentiment = total_score / count
        
        # Confidence based on agreement between tokens
        # If all tokens moving same direction = high confidence
        confidence = min(1.0, count / 3.0)
        
        return sentiment, confidence
    
    def get_btc_dominance_signal(self) -> float:
        """
        BTC Dominance as sentiment indicator:
        - BTC dominance rising = retail fleeing to BTC (fear)
        - BTC dominance falling = alt season (greed)
        
        Returns: -50 to +50 (bearish to bullish)
        """
        metrics = self.get_global_metrics()
        if not metrics:
            return 0.0
        
        btc_dom = metrics.get("btc_dominance", 50)
        btc_dom_yesterday = btc_dom - (metrics.get("btc_dominance_24h_percentage_change", 0))
        
        # Normal: 45-60 range
        # Below 50 = alt season (greed +50)
        # Above 55 = BTC safe haven (fear -50)
        normalized = 50 - btc_dom
        normalized = max(-50, min(50, normalized * 10))
        
        return normalized
    
    def calculate_composite_signal(self) -> Dict:
        """
        Calculate composite sentiment signal
        Returns dict with all components and final score
        """
        # Fetch all signals
        fg_value, fg_timestamp = self.get_fear_greed_proxy()
        
        # Momentum sentiment
        social_score, social_confidence = self.get_sentiment_from_momentum()
        
        # BTC dominance signal
        btc_dom_signal = self.get_btc_dominance_signal()
        
        # Get current prices for reference
        prices = self.get_price_data(["BTC", "ETH", "BNB"])
        btc_price = prices.get("BTC", {}).get("quote", {}).get("USD", {}).get("price", 0)
        
        # === WEIGHTED COMPOSITE SIGNAL ===
        # Fear & Greed proxy: 40%
        fg_normalized = fg_value - 50  # 0-100 → -50 to +50
        
        # Momentum: 35%
        momentum_normalized = social_score * 50  # -1 to +1 → -50 to +50
        
        # BTC dominance: 25%
        # (direct market sentiment indicator)
        
        raw_score = (
            fg_normalized * 0.40 +
            momentum_normalized * 0.35 +
            btc_dom_signal * 0.25
        )
        
        # Apply momentum filter (prevent sudden reversals)
        prev_signal = self.signal_history[-1]["composite"] if self.signal_history else 0
        momentum_delta = raw_score - prev_signal
        
        if abs(momentum_delta) > 30:
            # Sudden reversal - reduce confidence, blend with prev
            raw_score = prev_signal + (momentum_delta * 0.5)
        
        # Clamp to -100 to +100
        composite = max(-100, min(100, raw_score))
        
        # Determine action
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
            "btc_dominance_signal": btc_dom_signal,
            "momentum_delta": momentum_delta,
            "composite": composite,
            "action": action,
            "prev_composite": prev_signal,
            "btc_price": btc_price,
            "prices": {s: prices.get(s, {}).get("quote", {}).get("USD", {}).get("price", 0) 
                      for s in ["BTC", "ETH", "BNB"]}
        }
        
        # Store in history
        self.signal_history.append(signal_data)
        if len(self.signal_history) > 288:  # 24h of 5-min cycles
            self.signal_history.pop(0)
        
        self.last_fetch = datetime.now()
        
        return signal_data
    
    def get_market_prices(self) -> Dict[str, float]:
        """Get current prices for all primary tokens"""
        prices = {}
        data = self._make_request(
            "/v1/cryptocurrency/quotes/latest",
            {"symbol": "BTC,ETH,BNB,USDT,USDC,FDUSD,USD1,USDe,CAKE,TWT"}
        )
        if data and "data" in data:
            for symbol, info in data["data"].items():
                quote = info.get("quote", {}).get("USD", {})
                prices[symbol] = quote.get("price", 0)
        return prices
    
    def get_signal_summary(self) -> str:
        """Get human-readable signal summary"""
        sig = self.calculate_composite_signal()
        prices = sig.get("prices", {})
        btc = prices.get("BTC", 0)
        
        return f"""
╔══════════════════════════════════════════╗
║         SENTIMENTSWIPE SIGNAL            ║
╠══════════════════════════════════════════╣
║ BTC Price:  ${btc:,.0f}                      ║
║ Fear & Greed: {sig['fear_greed']:.1f}/100              ║
║ Momentum: {sig['social_sentiment']:+.3f} ({sig['social_confidence']:.0%} conf)    ║
║ BTC Dom Signal: {sig['btc_dominance_signal']:+.1f}            ║
╠══════════════════════════════════════════╣
║ COMPOSITE: {sig['composite']:+.1f}                       ║
║ ACTION: {sig['action']}               ║
╚══════════════════════════════════════════╝
"""