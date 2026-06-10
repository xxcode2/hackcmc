"""
SENTIMENTSWIPE V2 - Main Trading Agent
Orchestrates signal engine + risk manager + TWAK executor
"""

import os
import sys
import time
import logging
import schedule
from datetime import datetime
from typing import Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import modules
from signals.signal_engine import SignalEngine
from risk_manager.risk_engine import RiskManager, RiskState
from executor.twak_executor import TWAKExecutor, TxResult
from config.config import (
    CMC_API_KEY, AGENT_PRIVATE_KEY, TRADING_PAIR,
    CYCLE_INTERVAL_MINUTES, DAILY_GAS_BUDGET,
    COMPETITION_START, COMPETITION_END,
    PRIMARY_TOKENS
)

# Setup logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/sentimentswipe.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SentimentSwipeAgent:
    """
    Main trading agent that:
    1. Fetches sentiment signals from CMC
    2. Makes trading decisions
    3. Executes via TWAK
    4. Manages risk
    """
    
    def __init__(self, starting_capital: float):
        self.starting_capital = starting_capital
        
        # Initialize components
        self.signal_engine = SignalEngine(CMC_API_KEY)
        self.risk_manager = RiskManager(starting_capital)
        self.executor = TWAKExecutor(AGENT_PRIVATE_KEY) if AGENT_PRIVATE_KEY else None
        
        # State
        self.is_running = False
        self.cycle_count = 0
        self.last_signal = None
        self.gas_spent_today = 0.0
        
        logger.info(f"SentimentSwipe V2 initialized | Capital: ${starting_capual:.2f}")
    
    def check_competition_window(self) -> bool:
        """Check if we're in the competition window"""
        now = datetime.now()
        start = datetime.fromisoformat(COMPETITION_START.replace("Z", "+00:00"))
        end = datetime.fromisoformat(COMPETITION_END.replace("Z", "+00:00"))
        
        in_window = start <= now <= end
        if not in_window:
            logger.info(f"Outside competition window ({start.date()} - {end.date()})")
        return in_window
    
    def get_market_prices(self) -> Dict[str, float]:
        """Get current prices for all primary tokens"""
        prices = {}
        data = self.signal_engine._make_request("/v2/quotes/latest", {
            "symbol": ",".join(PRIMARY_TOKENS),
            "convert": "USD"
        })
        if data and "data" in data:
            for symbol, info in data["data"].items():
                quote = info.get("quote", {}).get("USD", {})
                prices[symbol] = quote.get("price", 0)
        return prices
    
    def select_target_token(self, signal: Dict, prices: Dict[str, float]) -> Optional[str]:
        """
        Select best token to trade based on signal
        Returns: token symbol or None
        """
        action = signal.get("action", "NEUTRAL")
        composite = signal.get("composite", 0)
        
        if action == "NEUTRAL":
            return None
        
        # Priority tokens based on action
        if action in ["BUY_DIP", "ACCUMULATE"]:
            # Buy tokens that are down but have good liquidity
            candidates = ["BNB", "BTC", "ETH"]
            for token in candidates:
                if token in prices and prices[token] > 0:
                    logger.info(f"Selected {token} for {action}")
                    return token
        
        elif action in ["TAKE_PROFIT", "SLIGHT_BULLISH"]:
            # Already in position - check if we should take profit
            open_pos = self.risk_manager.positions
            if open_pos:
                # Take profit on best performer
                return open_pos[0].token
        
        return None
    
    def execute_trade(self, token: str, action: str, prices: Dict[str, float]) -> Optional[TxResult]:
        """
        Execute a trade based on signal
        """
        if not self.executor:
            logger.error("No executor configured - set AGENT_PRIVATE_KEY")
            return None
        
        # Get current price
        price = prices.get(token, 0)
        if price == 0:
            logger.error(f"No price for {token}")
            return None
        
        # Get current portfolio value
        portfolio_value = self.risk_manager.calculate_portfolio_value(prices, prices.get("BNB", 0))
        
        # Check risk limits
        can_trade, mode = self.risk_manager.can_trade()
        if not can_trade:
            logger.info(f"Cannot trade: {mode}")
            return None
        
        # Calculate position size
        signal_conf = abs(self.last_signal.get("composite", 0)) / 100 if self.last_signal else 0.5
        position_usd = self.risk_manager.calculate_position_size(portfolio_value, signal_conf)
        
        # Calculate quantity
        quantity = position_usd / price
        
        # Execute based on action
        if action in ["BUY_DIP", "ACCUMULATE"]:
            # Buy with quote currency (USDT or BNB)
            result = self.executor.swap_tokens(TRADING_PAIR, token, position_usd)
        
        elif action in ["TAKE_PROFIT", "SLIGHT_BULLISH"]:
            # Sell token for quote
            result = self.executor.swap_tokens(token, TRADING_PAIR, quantity)
        
        else:
            return None
        
        # Record position if successful
        if result.success and result.tx_hash:
            self.risk_manager.open_position(
                token=token,
                entry_price=price,
                quantity=quantity,
                entry_value=position_usd,
                tx_hash=result.tx_hash
            )
        
        return result
    
    def check_and_close_positions(self, prices: Dict[str, float]):
        """Check all positions for stop loss / take profit"""
        closed = self.risk_manager.check_all_positions(prices)
        
        for trade in closed:
            if trade.exit_reason in ["stop_loss", "trailing_stop"]:
                logger.warning(f"Closed {trade.token}: {trade.pnl_pct:.2%} ({trade.exit_reason})")
            else:
                logger.info(f"Took profit {trade.token}: {trade.pnl_pct:.2%}")
    
    def run_cycle(self):
        """
        Main agent cycle - runs every CYCLE_INTERVAL_MINUTES
        """
        self.cycle_count += 1
        logger.info(f"=== CYCLE {self.cycle_count} ===")
        
        try:
            # 1. Get current prices
            prices = self.get_market_prices()
            logger.info(f"Prices loaded: {len(prices)} tokens")
            
            # 2. Check open positions (stop loss / take profit)
            self.check_and_close_positions(prices)
            
            # 3. Calculate current portfolio value
            portfolio_value = self.risk_manager.calculate_portfolio_value(prices, prices.get("BNB", 0))
            logger.info(f"Portfolio: ${portfolio_value:.2f}")
            
            # 4. Check drawdown status
            drawdown_status = self.risk_manager.check_drawdown_status(portfolio_value)
            if drawdown_status == "EMERGENCY_EXIT":
                logger.critical("EMERGENCY EXIT ALL POSITIONS")
                self.executor and self.executor.swap_tokens()  # Close all via TWAK
                self.risk_manager.close_all_positions(prices, "emergency")
                self.is_running = False
                return
            
            # 5. Check trade allowance
            can_trade, mode = self.risk_manager.can_trade()
            if not can_trade:
                logger.info(f"Trading paused: {mode}")
                return
            
            # 6. Fetch signals
            signal = self.signal_engine.calculate_composite_signal()
            self.last_signal = signal
            logger.info(self.signal_engine.get_signal_summary())
            
            # 7. Select and execute trade
            target_token = self.select_target_token(signal, prices)
            if target_token:
                result = self.execute_trade(target_token, signal["action"], prices)
                if result:
                    logger.info(f"Trade result: {'SUCCESS' if result.success else 'FAILED'} | {result.tx_hash or result.error}")
            
            # 8. Check if competition is over
            if not self.check_competition_window():
                logger.info("Competition ended - running final checks")
                self.is_running = False
            
        except Exception as e:
            logger.error(f"Cycle error: {e}", exc_info=True)
    
    def register_for_competition(self) -> bool:
        """Register agent for Track 1 competition"""
        if not self.executor:
            logger.error("No executor - cannot register")
            return False
        
        result = self.executor.register_competition()
        if result.success:
            logger.info(f"Registered for competition: {result.tx_hash}")
            return True
        else:
            logger.error(f"Registration failed: {result.error}")
            return False
    
    def start(self):
        """Start the agent"""
        logger.info("SENTIMENTSWIPE V2 STARTING...")
        
        # Verify setup
        if self.executor:
            setup = self.executor.verify_setup()
            logger.info(f"TWAK Setup: {setup}")
        
        self.is_running = True
        
        # Schedule cycles
        schedule.every(CYCLE_INTERVAL_MINUTES).minutes.do(self.run_cycle)
        
        # Initial cycle
        self.run_cycle()
        
        # Keep running
        while self.is_running:
            schedule.run_pending()
            time.sleep(1)
        
        logger.info("Agent stopped")
    
    def stop(self):
        """Stop the agent"""
        logger.info("Stopping agent...")
        self.is_running = False
    
    def get_status(self) -> Dict:
        """Get agent status for dashboard"""
        prices = self.get_market_prices() if self.is_running else {}
        portfolio_value = self.risk_manager.calculate_portfolio_value(
            prices, prices.get("BNB", 0)
        ) if prices else self.starting_capital
        
        return {
            "running": self.is_running,
            "cycle": self.cycle_count,
            "portfolio_value": portfolio_value,
            "starting_capital": self.starting_capital,
            "pnl": portfolio_value - self.starting_capital,
            "pnl_pct": (portfolio_value - self.starting_capital) / self.starting_capital * 100,
            "drawdown": self.risk_manager.get_drawdown(portfolio_value),
            "open_positions": len(self.risk_manager.positions),
            "trades_today": self.risk_manager.daily_trades,
            "total_trades": len(self.risk_manager.trade_history),
            "conservation_mode": self.risk_manager.conservation_mode,
            "last_signal": self.last_signal,
            "wallet_address": self.executor.get_wallet_address() if self.executor else None
        }


# === CLI INTERFACE ===

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="SentimentSwipe V2 Trading Agent")
    parser.add_argument("--capital", type=float, default=100.0, help="Starting capital in USD")
    parser.add_argument("--register", action="store_true", help="Register for competition")
    parser.add_argument("--status", action="store_true", help="Show agent status")
    args = parser.parse_args()
    
    agent = SentimentSwipeAgent(starting_capital=args.capital)
    
    if args.register:
        success = agent.register_for_competition()
        sys.exit(0 if success else 1)
    
    if args.status:
        status = agent.get_status()
        print(status)
        sys.exit(0)
    
    # Start agent
    agent.start()


if __name__ == "__main__":
    main()