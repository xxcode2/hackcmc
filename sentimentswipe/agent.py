"""
SENTIMENTSWIPE V2 - Main Trading Agent
Orchestrates signal engine + risk manager + executor
"""

import os
import sys
import time
import json
import logging
import schedule
from datetime import datetime, timezone
from typing import Dict, Optional

from signals.signal_engine import SignalEngine
from risk_manager.risk_engine import RiskManager
from executor.web3_executor import Web3Executor
from executor.twak_executor import TWAKExecutor
from config.config import (
    CMC_API_KEY, AGENT_PRIVATE_KEY, TRADING_PAIR,
    CYCLE_INTERVAL_MINUTES, DAILY_GAS_BUDGET,
    COMPETITION_START, COMPETITION_END, PRIMARY_TOKENS,
    MAX_DRAWDOWN, DISQUALIFICATION_DRAWDOWN, BASE_POSITION_PCT,
    STOP_LOSS_PCT, TAKE_PROFIT_PCT
)

# Setup logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/sentimentswipe.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SentimentSwipeAgent:
    """
    Main trading agent:
    1. Fetches sentiment signals from CMC
    2. Makes trading decisions
    3. Executes via Web3/TWAK
    4. Manages risk
    """

    def __init__(self, starting_capital: float = 100.0, private_key: str = None):
        self.starting_capital = starting_capital

        # Initialize components
        self.signal_engine = SignalEngine(CMC_API_KEY)
        self.risk_manager = RiskManager(starting_capital)

        # Try TWAK first, fallback to Web3
        self.private_key = private_key or AGENT_PRIVATE_KEY
        self.executor = None

        if self.private_key and len(self.private_key) == 64:
            try:
                twak = TWAKExecutor(self.private_key)
                if twak.verify_setup().get("twak_installed"):
                    self.executor = twak
                    logger.info("TWAK Executor active")
            except:
                pass

            if not self.executor:
                try:
                    self.executor = Web3Executor(self.private_key, starting_capital)
                    logger.info("Web3 Executor active")
                except Exception as e:
                    logger.error(f"Executor init failed: {e}")

        # State
        self.is_running = False
        self.cycle_count = 0
        self.last_signal = None
        self.last_prices = {}
        self.gas_spent_today = 0.0

        logger.info(f"SentimentSwipe V2 ready | Capital: ${starting_capital:.2f}")
        if self.executor:
            addr = self.executor.get_wallet_address()
            logger.info(f"Agent wallet: {addr}")

    def check_competition_window(self) -> bool:
        """Check if we're in the competition window"""
        now = datetime.now(timezone.utc)
        try:
            start = datetime.fromisoformat(COMPETITION_START.replace("Z", "+00:00"))
            end = datetime.fromisoformat(COMPETITION_END.replace("Z", "+00:00"))
        except:
            # Manual dates - competition window check
            start = datetime(2026, 6, 22, tzinfo=timezone.utc)
            end = datetime(2026, 6, 28, tzinfo=timezone.utc)

        in_window = start <= now <= end
        return in_window

    def get_market_prices(self) -> Dict[str, float]:
        """Get current prices from CMC"""
        return self.signal_engine.get_market_prices()

    def calculate_portfolio_value(self) -> float:
        """Calculate current portfolio value in USD"""
        if not self.executor:
            # Estimate from signal engine data
            prices = self.last_prices
            btc = prices.get("BTC", 61000)
            bnb = prices.get("BNB", 580)
            base_value = self.starting_capital

            # Rough estimate based on signal
            if self.last_signal:
                sig = self.last_signal["composite"]
                if sig > 20:
                    return base_value * 1.05  # slight gain
                elif sig < -20:
                    return base_value * 0.95  # slight loss
            return base_value

        return self.executor.get_portfolio_value(self.last_prices)

    def select_trade(self, signal: Dict, prices: Dict[str, float]) -> Optional[tuple]:
        """
        Select trade based on signal.
        Returns: (token, side, position_size_usd) or None
        """
        action = signal.get("action", "NEUTRAL")
        composite = signal.get("composite", 0)

        if action == "NEUTRAL":
            # Check if existing positions should be held
            return None

        portfolio_value = self.calculate_portfolio_value()

        # Calculate position size
        confidence = abs(composite) / 100
        pos_size = portfolio_value * BASE_POSITION_PCT
        pos_size *= (0.5 + confidence)  # confidence multiplier

        # Cap at 20%
        pos_size = min(pos_size, portfolio_value * 0.20)

        if action in ["BUY_DIP", "ACCUMULATE"]:
            # Buy candidates: BTC, ETH, BNB in fear
            for token in ["BTC", "ETH", "BNB"]:
                price = prices.get(token, 0)
                if price > 0:
                    return (token, "BUY", pos_size)

        elif action in ["TAKE_PROFIT", "SLIGHT_BULLISH"]:
            # Check if we have positions to take profit on
            if self.risk_manager.positions:
                # Take profit on best performer
                best = self.risk_manager.positions[0]
                return (best.token, "SELL", best.quantity)

        return None

    def execute_trade(self, token: str, side: str, size_usd: float) -> bool:
        """Execute a trade"""
        if not self.executor:
            logger.warning("No executor - cannot trade")
            return False

        price = self.last_prices.get(token, 0)
        if price == 0:
            logger.error(f"No price for {token}")
            return False

        # Amount in token units
        if side == "BUY":
            amount = size_usd / price
            # Buy token with USDT (or BNB)
            quote_token = "USDT"  # Most liquid pair
            result = self.executor.swap(quote_token, token, size_usd)
        else:
            # SELL - get balance of token
            balances = self.executor.get_balances()
            amount = balances.get(token, 0) * 0.5  # Sell 50% of holdings
            if amount <= 0:
                return False
            result = self.executor.swap(token, "USDT", amount)

        if result.success:
            logger.info(f"Trade SUCCESS: {side} {amount:.4f} {token} | tx: {result.tx_hash}")
            return True
        else:
            logger.error(f"Trade FAILED: {result.error}")
            return False

    def run_cycle(self):
        """Main agent cycle - runs every CYCLE_INTERVAL_MINUTES"""
        self.cycle_count += 1
        logger.info(f"=== CYCLE {self.cycle_count} | {datetime.now().strftime('%H:%M:%S')} ===")

        try:
            # 1. Get prices
            self.last_prices = self.get_market_prices()
            logger.info(f"Prices: BTC ${self.last_prices.get('BTC', 0):,.0f} | "
                       f"ETH ${self.last_prices.get('ETH', 0):,.0f} | "
                       f"BNB ${self.last_prices.get('BNB', 0):,.0f}")

            # 2. Check open positions (stop loss / take profit)
            if self.executor and self.last_prices:
                closed = self.risk_manager.check_all_positions(self.last_prices)
                for trade in closed:
                    logger.info(f"Closed {trade.token}: {trade.pnl_pct:.2%} ({trade.exit_reason})")

            # 3. Calculate portfolio value
            portfolio_value = self.calculate_portfolio_value()
            logger.info(f"Portfolio: ${portfolio_value:.2f}")

            # 4. Check drawdown
            drawdown_status = self.risk_manager.check_drawdown_status(portfolio_value)
            if drawdown_status == "EMERGENCY_EXIT":
                logger.critical("DRAWDOWN CRITICAL - EMERGENCY EXIT")
                if self.executor:
                    for pos in self.risk_manager.positions[:]:
                        self.executor.swap(pos.token, "USDT", pos.quantity)
                self.risk_manager.close_all_positions(self.last_prices, "emergency")
                self.is_running = False
                return

            if drawdown_status == "CONSERVATION":
                logger.warning("Conservation mode active")

            # 5. Check trade allowance
            can_trade, mode = self.risk_manager.can_trade()
            if not can_trade:
                logger.info(f"Trading paused: {mode}")
            else:
                # 6. Fetch signals
                signal = self.signal_engine.calculate_composite_signal()
                self.last_signal = signal
                print(self.signal_engine.get_signal_summary())

                # 7. Select and execute trade
                trade = self.select_trade(signal, self.last_prices)
                if trade:
                    token, side, size = trade
                    logger.info(f"Executing: {side} {size:.2f} of {token}")
                    self.execute_trade(token, side, size)
                else:
                    logger.info("No trade signal this cycle")

            # 8. Check competition window
            if not self.check_competition_window():
                logger.info("Outside competition window - running in paper mode")

            # 9. Save state
            self._save_state()

        except Exception as e:
            logger.error(f"Cycle error: {e}", exc_info=True)

    def _save_state(self):
        """Save agent state to file for dashboard"""
        state = {
            "portfolio_value": self.calculate_portfolio_value(),
            "starting_capital": self.starting_capital,
            "pnl": self.calculate_portfolio_value() - self.starting_capital,
            "pnl_pct": (self.calculate_portfolio_value() - self.starting_capital) / self.starting_capital * 100,
            "drawdown": self.risk_manager.get_drawdown(self.calculate_portfolio_value()),
            "open_positions": [
                {"token": p.token, "entry": p.entry_price, "value": p.entry_value}
                for p in self.risk_manager.positions
            ],
            "trades": self.risk_manager.export_trade_log(),
            "last_signal": self.last_signal,
            "running": self.is_running,
            "cycle": self.cycle_count,
            "wallet_address": self.executor.get_wallet_address() if self.executor else None
        }
        os.makedirs("logs", exist_ok=True)
        with open("logs/agent_state.json", "w") as f:
            json.dump(state, f, indent=2)

    def register_for_competition(self) -> bool:
        """Register agent for Track 1 (requires TWAK)"""
        if not self.executor:
            logger.error("Need executor for registration")
            return False

        try:
            if hasattr(self.executor, 'register_competition'):
                result = self.executor.register_competition()
                return result.success
        except Exception as e:
            logger.error(f"Registration failed: {e}")
        return False

    def start(self):
        """Start the agent"""
        logger.info("SENTIMENTSWIPE V2 STARTING...")
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
        """Get agent status"""
        return {
            "running": self.is_running,
            "cycle": self.cycle_count,
            "portfolio_value": self.calculate_portfolio_value(),
            "pnl": self.calculate_portfolio_value() - self.starting_capital,
            "drawdown": self.risk_manager.get_drawdown(self.calculate_portfolio_value()),
            "conservation_mode": self.risk_manager.conservation_mode,
            "emergency_pause": self.risk_manager.emergency_pause,
            "wallet": self.executor.get_wallet_address() if self.executor else None
        }


# === PAPER TRADING MODE (no real wallet needed) ===

class PaperTradingAgent(SentimentSwipeAgent):
    """Paper trading version - simulates trades without real transactions"""

    def __init__(self, starting_capital: float = 100.0):
        super().__init__(starting_capital, private_key=None)
        logger.info("PAPER TRADING MODE - No real trades")

    def execute_trade(self, token: str, side: str, size_usd: float) -> bool:
        """Simulate trade"""
        price = self.last_prices.get(token, 0)
        if price == 0:
            return False

        amount = size_usd / price

        if side == "BUY":
            # Simulate buying
            logger.info(f"[PAPER] BUY {amount:.6f} {token} @ ${price:.2f} = ${size_usd:.2f}")
            # Record as open position
            self.risk_manager.open_position(token, price, amount, size_usd)
        else:
            # Simulate selling
            logger.info(f"[PAPER] SELL {amount:.6f} {token} @ ${price:.2f}")
            # Close position (simplified)
            if self.risk_manager.positions:
                self.risk_manager.positions.pop(0)

        return True


# === CLI INTERFACE ===

def main():
    import argparse

    parser = argparse.ArgumentParser(description="SentimentSwipe V2 Trading Agent")
    parser.add_argument("--capital", type=float, default=100.0, help="Starting capital USD")
    parser.add_argument("--key", type=str, default=None, help="Private key (hex)")
    parser.add_argument("--register", action="store_true", help="Register for competition")
    parser.add_argument("--status", action="store_true", help="Show status and exit")
    parser.add_argument("--paper", action="store_true", help="Paper trading mode")
    parser.add_argument("--once", action="store_true", help="Run one cycle only")
    args = parser.parse_args()

    # Create agent
    if args.paper:
        agent = PaperTradingAgent(starting_capital=args.capital)
    else:
        agent = SentimentSwipeAgent(
            starting_capital=args.capital,
            private_key=args.key
        )

    if args.status:
        status = agent.get_status()
        print(json.dumps(status, indent=2, default=str))
        sys.exit(0)

    if args.register:
        success = agent.register_for_competition()
        sys.exit(0 if success else 1)

    if args.once:
        agent.run_cycle()
        sys.exit(0)

    # Start agent
    agent.start()


if __name__ == "__main__":
    main()