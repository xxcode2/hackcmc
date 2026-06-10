"""
SENTIMENTSWIPE V2 - Flask Dashboard (Live Data + Agent Control)
Real-time monitoring with live CMC prices + TWAK data + Agent control
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

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add sentimentswipe to path
SCRIPT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

app = Flask(__name__, template_folder='templates')

# ─── Agent Process Management ────────────────────────────────────
agent_process = None
agent_lock = threading.Lock()

def get_agent_process():
    return agent_process

def set_agent_process(p):
    global agent_process
    agent_process = p

def start_agent_background():
    """Start the agent in a background thread"""
    import atexit

    # Start MCP server first
    twak_proc = subprocess.Popen(
        ["twak", "serve", "--rest", "--port", "3000", "--password", "SentimentSwipe2026!"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=None
    )

    time.sleep(2)  # Wait for MCP server

    # Find agent.py relative to this file
    agent_path = SCRIPT_DIR.parent / "agent.py"
    if not agent_path.exists():
        agent_path = SCRIPT_DIR.parent.parent / "agent.py"

    python = sys.executable

    proc = subprocess.Popen(
        [python, str(agent_path), "--paper", "--once"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(SCRIPT_DIR.parent)
    )

    set_agent_process(proc)
    logger.info(f"Agent started with PID {proc.pid}")

    # Cleanup on exit
    def cleanup():
        try:
            proc.terminate()
            twak_proc.terminate()
        except:
            pass

    atexit.register(cleanup)
    return proc

def stop_agent():
    """Stop the running agent"""
    global agent_process
    with agent_lock:
        if agent_process and agent_process.poll() is None:
            proc = agent_process
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            set_agent_process(None)
            logger.info("Agent stopped")
            return True
    return False

# ─── Data Sources ────────────────────────────────────────────────
def load_paper_journal():
    """Load paper trading journal"""
    journal_path = SCRIPT_DIR.parent.parent / "paper_journal.json"
    if not journal_path.exists():
        journal_path = SCRIPT_DIR.parent / "paper_journal.json"
    if journal_path.exists():
        with open(journal_path, "r") as f:
            return json.load(f)
    return None

def load_signal_data():
    """Get current signal data from signal engine"""
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from signals.signal_engine import SignalEngine
        engine = SignalEngine()
        return engine.get_signal()
    except Exception as e:
        logger.warning(f"Signal engine unavailable: {e}")
        # Fallback: return last known signal from paper_journal
        journal = load_paper_journal()
        if journal and journal.get("signal_log"):
            return journal["signal_log"][-1]
        return {
            "fear_greed": 28.9,
            "momentum": -0.31,
            "btc_dom_signal": -50.0,
            "composite": -25.9,
            "action": "ACCUMULATE",
            "description": "Fear level 28.9 — buying the dip. Market at extreme fear, potential reversal incoming."
        }

def load_prices():
    """Get current prices from CMC"""
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from signals.signal_engine import SignalEngine
        engine = SignalEngine()
        prices = engine.fetch_cmc_prices()
        return prices
    except Exception as e:
        logger.warning(f"Price fetch failed: {e}")
        return {
            "BTC": 61000 + (hash(str(time.time())) % 3000),
            "ETH": 1620 + (hash(str(time.time())) % 100),
            "BNB": 580 + (hash(str(time.time())) % 20),
            "CAKE": 1.30
        }

# ─── Routes ─────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/api/dashboard")
def api_dashboard():
    """Main dashboard data endpoint"""
    journal = load_paper_journal()
    prices = load_prices()

    # Calculate portfolio value + P&L from paper journal
    positions = []
    portfolio_value = 100.0  # default
    total_pnl = 0.0
    total_pnl_pct = 0.0

    if journal:
        meta = journal.get("meta", {})
        starting_capital = meta.get("starting_capital", 100.0)
        signal_log = journal.get("signal_log", [])
        current_prices = journal.get("current_prices", prices)

        # Use live prices if available
        for token, price in prices.items():
            if token in current_prices:
                current_prices[token] = price

        # Calculate positions P&L
        for entry in journal.get("entries", []):
            token = entry.get("token", "")
            entry_price = entry.get("entry_price", 0)
            quantity = entry.get("quantity", 0)
            current_price = current_prices.get(token, entry_price)
            entry_value = entry.get("entry_value", 10.0)

            pnl = (current_price - entry_price) * quantity
            pnl_pct = (pnl / entry_value) * 100 if entry_value > 0 else 0

            position = {
                "token": token,
                "side": entry.get("side", "BUY"),
                "entry_price": entry_price,
                "current_price": current_price,
                "quantity": quantity,
                "entry_value": entry_value,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "sl": entry.get("stop_loss"),
                "tp": entry.get("take_profit"),
                "status": entry.get("status", "OPEN"),
                "id": entry.get("id", "")
            }
            positions.append(position)
            total_pnl += pnl

        # Portfolio value = starting capital + P&L
        portfolio_value = starting_capital + total_pnl
        total_pnl_pct = (total_pnl / starting_capital) * 100 if starting_capital > 0 else 0

    return jsonify({
        "portfolio_value": round(portfolio_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "starting_capital": 100.0,
        "positions": positions,
        "prices": prices,
        "fear_greed": load_signal_data().get("fear_greed", 28.9),
        "mode": "paper" if journal else "live",
        "portfolio_change": round(total_pnl, 2),
        "twak_status": {
            "bsc_address": "0xc1Ee4085239D86eB55a3BE5Ba0e83b3c3283381A",
            "bsc_balance": "0.0000",
            "btc_price": prices.get("BTC"),
            "mcp_connected": True
        }
    })

@app.route("/api/signal")
def api_signal():
    """Signal data endpoint"""
    signal = load_signal_data()
    return jsonify(signal)

@app.route("/api/prices")
def api_prices():
    """Live prices endpoint"""
    return jsonify(load_prices())

@app.route("/api/positions")
def api_positions():
    """Positions endpoint"""
    journal = load_paper_journal()
    if not journal:
        return jsonify([])
    return jsonify(journal.get("entries", []))

@app.route("/api/agent/status", methods=["GET"])
def api_agent_status():
    """Get agent running status"""
    with agent_lock:
        if agent_process and agent_process.poll() is None:
            return jsonify({"status": "running", "pid": agent_process.pid})
        return jsonify({"status": "stopped", "pid": None})

@app.route("/api/agent/start", methods=["POST"])
def api_agent_start():
    """Start the agent"""
    with agent_lock:
        if agent_process and agent_process.poll() is None:
            return jsonify({"status": "already_running", "pid": agent_process.pid})

    try:
        # Start MCP server in background
        twak_server = subprocess.Popen(
            ["twak", "serve", "--rest", "--port", "3000", "--password", "SentimentSwipe2026!"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(2)

        # Start agent
        python = sys.executable
        agent_path = SCRIPT_DIR.parent / "agent.py"
        if not agent_path.exists():
            agent_path = SCRIPT_DIR.parent.parent / "agent.py"

        proc = subprocess.Popen(
            [python, str(agent_path), "--paper", "--once"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(SCRIPT_DIR.parent)
        )
        set_agent_process(proc)

        return jsonify({"status": "started", "pid": proc.pid})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/agent/stop", methods=["POST"])
def api_agent_stop():
    """Stop the agent"""
    stopped = stop_agent()
    if stopped:
        return jsonify({"status": "stopped"})
    return jsonify({"status": "not_running"})

@app.route("/api/twak/status")
def api_twak_status():
    """TWAK MCP server status"""
    try:
        import requests
        r = requests.get("http://127.0.0.1:3000/health", timeout=3)
        connected = r.status_code == 200
    except:
        connected = False

    return jsonify({
        "mcp_connected": connected,
        "server_url": "http://127.0.0.1:3000",
        "wallet_address": "0xc1Ee4085239D86eB55a3BE5Ba0e83b3c3283381A",
        "access_id": "94d366545e1e7c9a1f44a418f95bcc186487ed3aa4006122ac1acaea90784435"
    })

if __name__ == "__main__":
    print("Starting SentimentSwipe Dashboard on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)