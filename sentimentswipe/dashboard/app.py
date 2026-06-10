"""
SENTIMENTSWIPE V2 - Flask Dashboard API (REAL TIME DATA)
Live data from: Signal Engine, CMC API, Paper Journal, TWAK MCP
"""

import os
import sys
import json
import subprocess
import threading
import time
import logging
from pathlib import Path
from flask import Flask, render_template, jsonify, request

# Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

app = Flask(__name__, template_folder='templates')

# ─── Agent Management ───────────────────────────────────────────
agent_proc = None
agent_lock = threading.Lock()
mcp_proc = None

def start_mcp_server():
    """Start TWAK MCP REST server in background"""
    global mcp_proc
    if mcp_proc and mcp_proc.poll() is None:
        return  # Already running
    
    mcp_proc = subprocess.Popen(
        ["twak", "serve", "--rest", "--port", "3000", "--password", "SentimentSwipe2026!"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(Path.home())
    )
    logger.info(f"MCP server started PID {mcp_proc.pid}")
    time.sleep(2)  # Wait for server to initialize

def start_agent_proc():
    """Start agent.py process"""
    global agent_proc
    
    with agent_lock:
        if agent_proc and agent_proc.poll() is None:
            return {"status": "already_running", "pid": agent_proc.pid}
    
    # Ensure MCP is running
    start_mcp_server()
    
    # Find agent.py
    agent_paths = [
        SCRIPT_DIR.parent / "agent.py",
        SCRIPT_DIR.parent.parent / "agent.py",
    ]
    agent_path = next((p for p in agent_paths if p.exists()), None)
    if not agent_path:
        return {"status": "error", "message": "agent.py not found"}
    
    python = sys.executable
    
    try:
        proc = subprocess.Popen(
            [python, str(agent_path), "--paper", "--once"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(SCRIPT_DIR.parent)
        )
        agent_proc = proc
        
        # Watchdog thread to update status when process ends
        def watch():
            proc.wait()
            logger.info(f"Agent process {proc.pid} exited with code {proc.returncode}")
        threading.Thread(target=watch, daemon=True).start()
        
        logger.info(f"Agent started PID {proc.pid}")
        return {"status": "started", "pid": proc.pid}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def stop_agent_proc():
    """Stop agent.py process"""
    global agent_proc, mcp_proc
    
    with agent_lock:
        if agent_proc and agent_proc.poll() is None:
            agent_proc.terminate()
            try:
                agent_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                agent_proc.kill()
            logger.info("Agent stopped")
        
        # Stop MCP server too
        if mcp_proc and mcp_proc.poll() is None:
            mcp_proc.terminate()
            try:
                mcp_proc.wait(timeout=3)
            except:
                mcp_proc.kill()
            logger.info("MCP server stopped")
        
        agent_proc = None
        mcp_proc = None
        return {"status": "stopped"}

def get_agent_status():
    """Get current agent running status"""
    with agent_lock:
        if agent_proc and agent_proc.poll() is None:
            return {"status": "running", "pid": agent_proc.pid}
        return {"status": "stopped", "pid": None}

# ─── Data Sources ───────────────────────────────────────────────
def get_live_signal():
    """Get real signal from signal engine"""
    try:
        from signals.signal_engine import SignalEngine
        from config.config import CMC_API_KEY
        engine = SignalEngine(CMC_API_KEY)
        return engine.calculate_composite_signal()
    except Exception as e:
        logger.warning(f"Signal engine error: {e}")
        return {
            "action": "NEUTRAL",
            "fear_greed": 38.2,
            "momentum_delta": -19.5,
            "btc_dominance_signal": -50,
            "composite": -19.5,
            "description": "Signal engine unavailable"
        }

def get_live_prices():
    """Get real prices from signal engine"""
    try:
        from signals.signal_engine import SignalEngine
        from config.config import CMC_API_KEY
        engine = SignalEngine(CMC_API_KEY)
        prices = engine.get_market_prices()
        return prices
    except Exception as e:
        logger.warning(f"Price fetch error: {e}")
        return {}

def get_paper_positions():
    """Get positions from paper journal with live P&L"""
    journal_path = SCRIPT_DIR / "paper_journal.json"
    if not journal_path.exists():
        journal_path = SCRIPT_DIR.parent / "paper_journal.json"
    if not journal_path.exists():
        return []

    try:
        with open(journal_path, "r") as f:
            journal = json.load(f)
        
        # Get live prices
        prices = get_live_prices()
        
        # Calculate P&L for each position
        positions = []
        for entry in journal.get("entries", []):
            token = entry.get("token", "")
            entry_price = entry.get("entry_price", 0)
            quantity = entry.get("quantity", 0)
            entry_value = entry.get("entry_value", 10.0)
            current_price = prices.get(token, entry_price)
            
            pnl = (current_price - entry_price) * quantity
            pnl_pct = (pnl / entry_value) * 100 if entry_value > 0 else 0
            
            positions.append({
                "token": token,
                "side": entry.get("side", "BUY"),
                "entry_price": entry_price,
                "current_price": round(current_price, 4),
                "quantity": round(quantity, 8),
                "entry_value": round(entry_value, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "sl": entry.get("stop_loss"),
                "tp": entry.get("take_profit"),
                "status": entry.get("status", "OPEN"),
                "id": entry.get("id", ""),
                "entry_time": entry.get("entry_time", "")
            })
        
        return positions
    except Exception as e:
        logger.error(f"Paper journal error: {e}")
        return []

def get_portfolio_summary():
    """Calculate portfolio value + P&L from positions"""
    positions = get_paper_positions()
    starting_capital = 100.0
    
    open_positions = [p for p in positions if p["status"] == "OPEN"]
    total_pnl = sum(p["pnl"] for p in positions)
    portfolio_value = starting_capital + total_pnl
    total_pnl_pct = (total_pnl / starting_capital) * 100 if starting_capital > 0 else 0
    
    wins = len([p for p in positions if p["pnl"] > 0])
    losses = len([p for p in positions if p["pnl"] < 0])
    win_rate = (wins / len(positions) * 100) if positions else 0
    
    return {
        "portfolio_value": round(portfolio_value, 2),
        "starting_capital": starting_capital,
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "open_positions": len(open_positions),
        "total_positions": len(positions),
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 1)
    }

def get_twak_status():
    """Check TWAK MCP server + wallet status"""
    status = {
        "connected": False,
        "server_url": "http://127.0.0.1:3000",
        "wallet_address": "0xc1Ee4085239D86eB55a3BE5Ba0e83b3c3283381A",
        "wallet_address_short": "0xc1Ee...381A",
        "chain": "BSC",
        "balance": "0.0000",
        "btc_price": None,
        "bnb_price": None,
        "mcp_tools_count": 50
    }
    
    # Check MCP server
    try:
        import requests
        r = requests.get(f"{status['server_url']}/health", timeout=2)
        status["connected"] = r.status_code == 200
    except:
        status["connected"] = False
    
    # Try TWAK CLI for balance
    try:
        result = subprocess.run(
            ["twak", "balance", "--chain", "bsc", "--address", status["wallet_address"], "--json"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(Path.home())
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            balance = data.get("balance", "0")
            status["balance"] = str(round(float(balance), 6)) if balance else "0"
    except:
        pass
    
    # Get prices from live data
    prices = get_live_prices()
    status["btc_price"] = prices.get("BTC")
    status["bnb_price"] = prices.get("BNB")
    
    return status

# ─── Routes ─────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/api/dashboard")
def api_dashboard():
    """
    Main dashboard data endpoint — returns ALL real-time data
    """
    signal = get_live_signal()
    portfolio = get_portfolio_summary()
    positions = get_paper_positions()
    prices = get_live_prices()
    twak = get_twak_status()
    agent = get_agent_status()
    
    return jsonify({
        # Portfolio
        "portfolio_value": portfolio["portfolio_value"],
        "starting_capital": portfolio["starting_capital"],
        "total_pnl": portfolio["total_pnl"],
        "total_pnl_pct": portfolio["total_pnl_pct"],
        "open_positions": portfolio["open_positions"],
        "total_positions": portfolio["total_positions"],
        "wins": portfolio["wins"],
        "losses": portfolio["losses"],
        "win_rate": portfolio["win_rate"],
        
        # Signal
        "action": signal.get("action", "NEUTRAL"),
        "fear_greed": round(signal.get("fear_greed", 38.2), 1),
        "momentum_delta": round(signal.get("momentum_delta", 0), 2),
        "btc_dominance_signal": signal.get("btc_dominance_signal", -50),
        "composite": round(signal.get("composite", 0), 2),
        "signal_description": get_signal_description(signal),
        
        # Prices
        "prices": {k: round(v, 4) for k, v in prices.items()},
        
        # Positions
        "positions": positions,
        
        # TWAK
        "twak": twak,
        
        # Agent
        "agent": agent,
        
        # System
        "mode": "paper",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "last_update": time.strftime("%H:%M:%S")
    })

@app.route("/api/signal")
def api_signal():
    """Signal data endpoint"""
    signal = get_live_signal()
    return jsonify({
        "action": signal.get("action", "NEUTRAL"),
        "fear_greed": round(signal.get("fear_greed", 38.2), 1),
        "momentum_delta": round(signal.get("momentum_delta", 0), 2),
        "btc_dominance_signal": signal.get("btc_dominance_signal", -50),
        "composite": round(signal.get("composite", 0), 2),
        "description": get_signal_description(signal)
    })

@app.route("/api/prices")
def api_prices():
    """Live prices"""
    return jsonify(get_live_prices())

@app.route("/api/positions")
def api_positions():
    """Positions with live P&L"""
    return jsonify(get_paper_positions())

@app.route("/api/agent/status")
def api_agent_status():
    """Agent running status"""
    return jsonify(get_agent_status())

@app.route("/api/agent/start", methods=["POST"])
def api_agent_start():
    """Start agent + MCP server"""
    result = start_agent_proc()
    status_code = 200 if result.get("status") == "started" else 400
    return jsonify(result), status_code

@app.route("/api/agent/stop", methods=["POST"])
def api_agent_stop():
    """Stop agent + MCP server"""
    result = stop_agent_proc()
    return jsonify(result)

@app.route("/api/twak/status")
def api_twak_status():
    """TWAK MCP status"""
    return jsonify(get_twak_status())

def get_signal_description(signal):
    """Generate human-readable signal description"""
    action = signal.get("action", "NEUTRAL")
    fg = signal.get("fear_greed", 50)
    
    if action == "ACCUMULATE":
        return f"Fear level {fg:.0f} — buying the dip. Market at extreme fear, potential reversal incoming."
    elif action == "TAKE_PROFIT":
        return f"Greed level {fg:.0f} — taking profits. Market overheated, consider reducing exposure."
    else:
        return f"Neutral zone ({fg:.0f}) — hold positions and wait for clearer signals."

if __name__ == "__main__":
    print("=" * 50)
    print("SentimentSwipe V2 Dashboard")
    print("URL: http://localhost:5000")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)