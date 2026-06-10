"""
SENTIMENTSWIPE V2 - Risk Manager
Handles drawdown protection, stop loss, position sizing, and emergency exits
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from config.config import (
    MAX_DRAWDOWN, DISQUALIFICATION_DRAWDOWN, STOP_LOSS_PCT,
    TAKE_PROFIT_PCT, TRAILING_STOP_PCT, DAILY_TRADE_LIMIT,
    MAX_POSITION_PCT, BASE_POSITION_PCT, MIN_POSITION_VALUE, MAX_POSITION_VALUE
)

logger = logging.getLogger(__name__)

@dataclass
class Position:
    """Represents an open position"""
    token: str
    entry_price: float
    quantity: float
    entry_time: datetime
    entry_value: float  # USD value at entry
    stop_loss: float
    take_profit: float
    trailing_stop: Optional[float] = None
    is_trailing_active: bool = False

@dataclass
class TradeResult:
    """Result of a completed or closed trade"""
    token: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl_pct: float
    pnl_usd: float
    exit_reason: str  # "stop_loss", "take_profit", "signal_reversal", "manual"
    exit_time: datetime
    tx_hash: str = ""

@dataclass
class RiskState:
    """Current risk state of the portfolio"""
    portfolio_value: float
    starting_value: float
    current_drawdown: float
    trades_today: int
    total_trades: int
    open_positions: List[Position]
    conservation_mode: bool
    emergency_pause: bool
    last_update: datetime = field(default_factory=datetime.now)

class RiskManager:
    """Manages all risk controls for the agent"""
    
    def __init__(self, starting_capital: float):
        self.starting_capital = starting_capital
        self.positions: List[Position] = []
        self.trade_history: List[TradeResult] = []
        self.daily_trades = 0
        self.last_trade_date = datetime.now().date()
        self.conservation_mode = False
        self.emergency_pause = False
        
    def _reset_daily_trades(self):
        """Reset daily trade counter if new day"""
        today = datetime.now().date()
        if today > self.last_trade_date:
            self.daily_trades = 0
            self.last_trade_date = today
    
    def calculate_portfolio_value(self, current_prices: Dict[str, float], bnb_price: float) -> float:
        """Calculate current portfolio value in USD"""
        # This should be called with current prices from exchange
        # For now, return starting value minus realized losses
        realized_pnl = sum(t.pnl_usd for t in self.trade_history)
        return self.starting_capital + realized_pnl
    
    def get_drawdown(self, current_value: float) -> float:
        """Calculate current drawdown from peak"""
        peak = max(self.starting_capital, current_value)
        return (peak - current_value) / peak
    
    def can_trade(self) -> tuple[bool, str]:
        """Check if a new trade is allowed"""
        self._reset_daily_trades()
        
        # Emergency pause check
        if self.emergency_pause:
            return False, "EMERGENCY PAUSE: Manual intervention required"
        
        # Conservation mode - still allow trades but reduced
        mode = "CONSERVATION" if self.conservation_mode else "NORMAL"
        
        # Daily trade limit
        if self.daily_trades >= DAILY_TRADE_LIMIT:
            return False, f"Daily trade limit reached ({DAILY_TRADE_LIMIT})"
        
        return True, mode
    
    def check_drawdown_status(self, current_value: float):
        """Check and update drawdown status"""
        drawdown = self.get_drawdown(current_value)
        
        if drawdown >= DISQUALIFICATION_DRAWDOWN:
            logger.critical(f"DRAWDOWN {drawdown:.1%} >= {DISQUALIFICATION_DRAWDOWN:.1%} - EMERGENCY EXIT")
            self.emergency_pause = True
            return "EMERGENCY_EXIT"
        
        elif drawdown >= MAX_DRAWDOWN:
            logger.warning(f"DRAWDOWN {drawdown:.1%} >= {MAX_DRAWDOWN:.1%} - Conservation mode")
            self.conservation_mode = True
            return "CONSERVATION"
        
        elif drawdown < MAX_DRAWDOWN * 0.5 and self.conservation_mode:
            # Recovered - exit conservation mode
            logger.info(f"Drawdown {drawdown:.1%} recovered - Normal mode")
            self.conservation_mode = False
            
        return "OK"
    
    def calculate_position_size(self, portfolio_value: float, signal_confidence: float = 1.0) -> float:
        """Calculate trade position size in USD"""
        # Conservation mode = half position
        if self.conservation_mode:
            effective_pct = BASE_POSITION_PCT * 0.5
        else:
            effective_pct = BASE_POSITION_PCT
        
        # Apply signal confidence multiplier (1.0x to 2.0x)
        confidence_mult = 0.5 + signal_confidence  # 0.5-1.5x range
        effective_pct *= confidence_mult
        
        # Cap at max position
        effective_pct = min(effective_pct, MAX_POSITION_PCT)
        
        position_usd = portfolio_value * effective_pct
        
        # Apply limits
        position_usd = max(MIN_POSITION_VALUE, min(MAX_POSITION_VALUE, position_usd))
        
        return position_usd
    
    def calculate_stop_loss(self, entry_price: float, is_long: bool = True) -> float:
        """Calculate stop loss price"""
        if is_long:
            return entry_price * (1 - STOP_LOSS_PCT)
        else:
            return entry_price * (1 + STOP_LOSS_PCT)
    
    def calculate_take_profit(self, entry_price: float, is_long: bool = True) -> float:
        """Calculate take profit price"""
        if is_long:
            return entry_price * (1 + TAKE_PROFIT_PCT)
        else:
            return entry_price * (1 - TAKE_PROFIT_PCT)
    
    def open_position(self, token: str, entry_price: float, quantity: float, 
                     entry_value: float, tx_hash: str = "") -> Position:
        """Open a new position"""
        pos = Position(
            token=token,
            entry_price=entry_price,
            quantity=quantity,
            entry_time=datetime.now(),
            entry_value=entry_value,
            stop_loss=self.calculate_stop_loss(entry_price),
            take_profit=self.calculate_take_profit(entry_price)
        )
        self.positions.append(pos)
        self.daily_trades += 1
        
        logger.info(f"Opened {token} position: {quantity} @ {entry_price}, SL: {pos.stop_loss:.6f}, TP: {pos.take_profit:.6f}")
        
        return pos
    
    def check_position_limits(self, token: str, current_value: float) -> Optional[str]:
        """Check if adding position to token exceeds limits"""
        # Check total position in token
        token_positions = [p for p in self.positions if p.token == token]
        current_exposure = sum(p.entry_value for p in token_positions)
        max_exposure = current_value * MAX_POSITION_PCT
        
        if current_exposure >= max_exposure:
            return f"Max position in {token} reached"
        return None
    
    def check_all_positions(self, current_prices: Dict[str, float]) -> List[TradeResult]:
        """Check all positions for stop loss / take profit triggers"""
        closed = []
        
        for pos in self.positions[:]:  # Copy list for safe removal
            current_price = current_prices.get(pos.token)
            if current_price is None:
                continue
            
            price_change = (current_price - pos.entry_price) / pos.entry_price
            pnl_pct = price_change
            pnl_usd = pos.entry_value * pnl_pct
            
            # Check trailing stop first (if active)
            if pos.is_trailing_active and pos.trailing_stop:
                if pos.entry_price > 0:
                    if pos.token.endswith("USDT") or "USD" in pos.token:
                        pass  # Stablecoin - no trailing stop needed
                    else:
                        # For tokens, check if price dropped from peak
                        trail_trigger = pos.trailing_stop
                
            # Check stop loss
            if current_price <= pos.stop_loss:
                result = TradeResult(
                    token=pos.token,
                    entry_price=pos.entry_price,
                    exit_price=current_price,
                    quantity=pos.quantity,
                    pnl_pct=pnl_pct,
                    pnl_usd=pnl_usd,
                    exit_reason="stop_loss",
                    exit_time=datetime.now(),
                    tx_hash=""
                )
                closed.append(result)
                self.positions.remove(pos)
                logger.warning(f"STOP LOSS hit for {pos.token}: {pnl_pct:.2%}")
                
            # Check take profit
            elif current_price >= pos.take_profit:
                # Activate trailing stop
                pos.is_trailing_active = True
                pos.trailing_stop = current_price * (1 - TRAILING_STOP_PCT)
                logger.info(f"TAKE PROFIT reached for {pos.token}, trailing stop: {pos.trailing_stop:.6f}")
                
            # Check trailing stop trigger
            elif pos.is_trailing_active and pos.trailing_stop:
                if current_price <= pos.trailing_stop:
                    result = TradeResult(
                        token=pos.token,
                        entry_price=pos.entry_price,
                        exit_price=current_price,
                        quantity=pos.quantity,
                        pnl_pct=pnl_pct,
                        pnl_usd=pnl_usd,
                        exit_reason="trailing_stop",
                        exit_time=datetime.now(),
                        tx_hash=""
                    )
                    closed.append(result)
                    self.positions.remove(pos)
                    logger.info(f"TRAILING STOP hit for {pos.token}: {pnl_pct:.2%}")
        
        self.trade_history.extend(closed)
        return closed
    
    def close_all_positions(self, current_prices: Dict[str, float], reason: str = "emergency") -> List[TradeResult]:
        """Emergency exit all positions"""
        results = []
        
        for pos in self.positions[:]:
            current_price = current_prices.get(pos.token, pos.entry_price)
            price_change = (current_price - pos.entry_price) / pos.entry_price
            pnl_pct = price_change
            pnl_usd = pos.entry_value * pnl_pct
            
            result = TradeResult(
                token=pos.token,
                entry_price=pos.entry_price,
                exit_price=current_price,
                quantity=pos.quantity,
                pnl_pct=pnl_pct,
                pnl_usd=pnl_usd,
                exit_reason=reason,
                exit_time=datetime.now(),
                tx_hash=""
            )
            results.append(result)
            
        self.trade_history.extend(results)
        self.positions.clear()
        
        logger.critical(f"EMERGENCY EXIT: Closed {len(results)} positions")
        return results
    
    def get_state(self, portfolio_value: float) -> RiskState:
        """Get current risk state"""
        return RiskState(
            portfolio_value=portfolio_value,
            starting_value=self.starting_capital,
            current_drawdown=self.get_drawdown(portfolio_value),
            trades_today=self.daily_trades,
            total_trades=len(self.trade_history),
            open_positions=self.positions.copy(),
            conservation_mode=self.conservation_mode,
            emergency_pause=self.emergency_pause
        )
    
    def get_stats(self) -> Dict:
        """Get trading statistics"""
        if not self.trade_history:
            return {"win_rate": 0, "total_pnl": 0, "avg_win": 0, "avg_loss": 0}
        
        wins = [t for t in self.trade_history if t.pnl_usd > 0]
        losses = [t for t in self.trade_history if t.pnl_usd <= 0]
        
        return {
            "total_trades": len(self.trade_history),
            "win_rate": len(wins) / len(self.trade_history) if self.trade_history else 0,
            "total_pnl": sum(t.pnl_usd for t in self.trade_history),
            "avg_win": sum(t.pnl_usd for t in wins) / len(wins) if wins else 0,
            "avg_loss": sum(t.pnl_usd for t in losses) / len(losses) if losses else 0,
            "best_trade": max((t.pnl_pct for t in self.trade_history), default=0),
            "worst_trade": min((t.pnl_pct for t in self.trade_history), default=0)
        }
    
    def export_trade_log(self) -> List[Dict]:
        """Export trade history as dict for logging/reporting"""
        return [
            {
                "token": t.token,
                "entry": t.entry_price,
                "exit": t.exit_price,
                "qty": t.quantity,
                "pnl_pct": f"{t.pnl_pct:.2%}",
                "pnl_usd": f"${t.pnl_usd:.2f}",
                "exit_reason": t.exit_reason,
                "time": t.exit_time.isoformat()
            }
            for t in self.trade_history
        ]