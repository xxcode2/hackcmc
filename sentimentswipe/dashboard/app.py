"""
SENTIMENTSWIPE V2 - Flask Dashboard (Live Data)
Real-time monitoring with live CMC prices + TWAK data
"""

import os
import sys
import json
from flask import Flask, render_template, jsonify, request
from datetime import datetime

# Add sentimentswipe to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

app = Flask(__name__)

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "agent_state.json")
PAPER_JOURNAL = os.path.join(os.path.dirname(__file__), "..", "paper_journal.json")

# Cache prices for 60 seconds
_prices_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 60

def get_cmc_prices():
    """Fetch live prices from CMC API"""
    global _prices_cache
    
    now = datetime.now().timestamp()
    if _prices_cache["data"] and (now - _prices_cache["timestamp"]) < CACHE_TTL:
        return _prices_cache["data"]
    
    try:
        import requests
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        params = {"symbol": "BTC,ETH,BNB,CAKE"}
        headers = {"X-CMC_PRO_API_KEY": "e234f83950e44af38f101284ec4692c1"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()["data"]
            prices = {
                "BTC": data["BTC"]["quote"]["USD"]["price"],
                "ETH": data["ETH"]["quote"]["USD"]["price"],
                "BNB": data["BNB"]["quote"]["USD"]["price"],
                "CAKE": data["CAKE"]["quote"]["USD"]["price"],
            }
            _prices_cache = {"data": prices, "timestamp": now}
            return prices
    except Exception as e:
        pass
    
    # Fallback cache
    return _prices_cache["data"] or {"BTC": 61000, "ETH": 1620, "BNB": 580, "CAKE": 1.30}

def load_paper_journal():
    """Load paper trading journal"""
    if os.path.exists(PAPER_JOURNAL):
        try:
            with open(PAPER_JOURNAL, "r") as f:
                return json.load(f)
        except:
            pass
    return {"entries": [], "positions": []}

def load_state():
    """Load agent state from disk"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {
        "portfolio_value": 100.0,
        "starting_capital": 100.0,
        "pnl": 0.0,
        "pnl_pct": 0.0,
        "drawdown": 0.0,
        "open_positions": [],
        "trades": [],
        "last_signal": {},
        "running": False
    }

def save_state(state):
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "logs"), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def get_live_signal():
    """Fetch live signal data"""
    try:
        from signals.signal_engine import SignalEngine
        engine = SignalEngine()
        signal = engine.get_signal()
        return signal
    except Exception as e:
        return {
            "fear_greed": 28.0,
            "momentum": -22.0,
            "composite": -25.0,
            "action": "ACCUMULATE"
        }

def calculate_positions_pnl(positions, prices):
    """Calculate real-time P&L for positions"""
    updated = []
    total_value = 0
    
    for pos in positions:
        symbol = pos.get("symbol", "").upper()
        if symbol in prices:
            current_price = prices[symbol]
        else:
            current_price = pos.get("current_price", pos.get("entry_price", 0))
        
        entry_price = pos["entry_price"]
        quantity = pos["quantity"]
        value = quantity * current_price
        entry_value = quantity * entry_price
        pnl_value = value - entry_value
        pnl_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
        
        stop_loss = pos.get("stop_loss", entry_price * 0.95)
        take_profit = pos.get("take_profit", entry_price * 1.10)
        
        updated.append({
            "id": pos.get("id"),
            "symbol": symbol,
            "name": pos.get("name", symbol),
            "entry_price": entry_price,
            "current_price": current_price,
            "quantity": quantity,
            "value": value,
            "pnl_value": pnl_value,
            "pnl_pct": pnl_pct,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "status": "active"
        })
        
        total_value += value
    
    return updated, total_value

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/api/status")
def api_status():
    """Return comprehensive live status"""
    try:
        state = load_state()
        prices = get_cmc_prices()
        signal = get_live_signal()
        journal = load_paper_journal()
        
        # Get positions from journal or state
        positions = state.get("open_positions", [])
        if not positions and journal.get("positions"):
            positions = journal["positions"]
        
        # Calculate P&L
        updated_positions, positions_value = calculate_positions_pnl(positions, prices)
        
        # Calculate portfolio
        starting_capital = state.get("starting_capital", 100.0)
        portfolio_value = state.get("portfolio_value", starting_capital)
        
        # If we have positions, track actual value
        if updated_positions:
            # Use tracked portfolio value + unrealized P&L
            unrealized_pnl = sum(p["pnl_value"] for p in updated_positions)
            portfolio_value = state.get("portfolio_value", starting_capital) + unrealized_pnl
        
        pnl = portfolio_value - starting_capital
        pnl_pct = (pnl / starting_capital * 100) if starting_capital > 0 else 0
        
        # Update drawdown tracking
        peak = state.get("peak_value", starting_capital)
        if portfolio_value > peak:
            peak = portfolio_value
            state["peak_value"] = peak
        
        drawdown = (peak - portfolio_value) / peak if peak > 0 else 0
        state["peak_value"] = peak
        state["portfolio_value"] = portfolio_value
        state["pnl"] = pnl
        state["pnl_pct"] = pnl_pct
        state["drawdown"] = drawdown
        state["open_positions"] = updated_positions
        state["last_signal"] = signal
        save_state(state)
        
        return jsonify({
            "portfolio_value": portfolio_value,
            "starting_capital": starting_capital,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "drawdown": drawdown,
            "open_positions": updated_positions,
            "trades_today": state.get("trades_today", len(journal.get("entries", []))),
            "trades": journal.get("entries", [])[-10:],
            "last_signal": signal,
            "prices": prices,
            "running": state.get("running", False),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "portfolio_value": 100.0, "pnl": 0.0, "pnl_pct": 0.0, "open_positions": [], "last_signal": {}, "running": False})

@app.route("/api/prices")
def api_prices():
    """Return live prices only"""
    prices = get_cmc_prices()
    return jsonify(prices)

@app.route("/api/signal")
def api_signal():
    signal = get_live_signal()
    return jsonify(signal)

@app.route("/api/trades")
def api_trades():
    journal = load_paper_journal()
    return jsonify(journal.get("entries", []))

@app.route("/api/start", methods=["POST"])
def api_start():
    state = load_state()
    state["running"] = True
    save_state(state)
    return jsonify({"status": "started", "running": True})

@app.route("/api/stop", methods=["POST"])
def api_stop():
    state = load_state()
    state["running"] = False
    save_state(state)
    return jsonify({"status": "stopped", "running": False})

@app.route("/api/twak-status")
def api_twak():
    """Return TWAK wallet status"""
    try:
        from executor.twak_native import twak_auth_status, twak_wallet_status, twak_get_wallet_address, twak_balance
        auth = twak_auth_status()
        wallet_status = twak_wallet_status()
        addr = twak_get_wallet_address()
        
        balance = {}
        if addr:
            bal = twak_balance(addr)
            balance = bal
        
        return jsonify({
            "auth": auth,
            "wallet": wallet_status,
            "address": addr,
            "balance": balance
        })
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)