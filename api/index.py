"""
SENTIMENTSWIPE V2 - Vercel Serverless Flask
All routes: / -> HTML, /api/* -> JSON
"""

import os
import sys
import json
import threading

# Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # hackcmc/
SENTIMENTSWIPE_DIR = os.path.join(BASE_DIR, 'sentimentswipe')
sys.path.insert(0, SENTIMENTSWIPE_DIR)

from flask import Flask, render_template, jsonify, request
from datetime import datetime

app = Flask(__name__, template_folder='../sentimentswipe/dashboard/templates')

# ─── Agent State (file-based for serverless) ───────────────────
STATE_FILE = os.path.join(SENTIMENTSWIPE_DIR, 'logs', 'agent_state.json')
PAPER_JOURNAL = os.path.join(SENTIMENTSWIPE_DIR, 'paper_journal.json')

agent_proc = None
agent_lock = threading.Lock()

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {
        "portfolio_value": 100.0, "starting_capital": 100.0,
        "pnl": 0.0, "pnl_pct": 0.0, "drawdown": 0.0,
        "open_positions": [], "trades": [], "running": False
    }

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)

# ─── Data Sources ───────────────────────────────────────────────
def get_live_signal():
    try:
        from signals.signal_engine import SignalEngine
        from config.config import CMC_API_KEY
        engine = SignalEngine(CMC_API_KEY)
        return engine.calculate_composite_signal()
    except Exception as e:
        return {"action": "NEUTRAL", "fear_greed": 38.0,
                "momentum_delta": -19.0, "btc_dominance_signal": -50,
                "composite": -19.0, "description": "Signal unavailable"}

def get_live_prices():
    try:
        from signals.signal_engine import SignalEngine
        from config.config import CMC_API_KEY
        engine = SignalEngine(CMC_API_KEY)
        return engine.get_market_prices()
    except:
        return {"BTC": 62000, "ETH": 1640, "BNB": 592, "CAKE": 1.31}

def get_paper_positions():
    if not os.path.exists(PAPER_JOURNAL):
        return []
    try:
        with open(PAPER_JOURNAL, "r") as f:
            journal = json.load(f)
        prices = get_live_prices()
        positions = []
        for entry in journal.get("entries", []):
            token = entry.get("token", "")
            ep = entry.get("entry_price", 0)
            qty = entry.get("quantity", 0)
            ev = entry.get("entry_value", 10.0)
            cp = prices.get(token, ep)
            pnl = (cp - ep) * qty
            pnl_pct = (pnl / ev) * 100 if ev > 0 else 0
            positions.append({
                "token": token, "side": entry.get("side", "BUY"),
                "entry_price": ep, "current_price": round(cp, 4),
                "quantity": round(qty, 8), "entry_value": round(ev, 2),
                "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2),
                "sl": entry.get("stop_loss"), "tp": entry.get("take_profit"),
                "status": entry.get("status", "OPEN"),
                "id": entry.get("id", ""), "entry_time": entry.get("entry_time", "")
            })
        return positions
    except:
        return []

def get_portfolio_summary():
    positions = get_paper_positions()
    starting = 100.0
    total_pnl = sum(p["pnl"] for p in positions)
    portfolio_value = starting + total_pnl
    total_pnl_pct = (total_pnl / starting) * 100 if starting > 0 else 0
    wins = len([p for p in positions if p["pnl"] > 0])
    losses = len([p for p in positions if p["pnl"] < 0])
    open_pos = len([p for p in positions if p["status"] == "OPEN"])
    return {
        "portfolio_value": round(portfolio_value, 2),
        "starting_capital": starting,
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "open_positions": open_pos,
        "total_positions": len(positions),
        "wins": wins, "losses": losses,
        "win_rate": round(wins / len(positions) * 100, 1) if positions else 0
    }

def get_agent_status():
    state = load_state()
    return {"status": "stopped", "pid": None, "running": state.get("running", False)}

# ─── Routes ─────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/api/dashboard")
def api_dashboard():
    signal = get_live_signal()
    portfolio = get_portfolio_summary()
    prices = get_live_prices()
    positions = get_paper_positions()
    agent = get_agent_status()

    return jsonify({
        "portfolio_value": portfolio["portfolio_value"],
        "starting_capital": portfolio["starting_capital"],
        "total_pnl": portfolio["total_pnl"],
        "total_pnl_pct": portfolio["total_pnl_pct"],
        "open_positions": portfolio["open_positions"],
        "total_positions": portfolio["total_positions"],
        "wins": portfolio["wins"],
        "losses": portfolio["losses"],
        "win_rate": portfolio["win_rate"],
        "action": signal.get("action", "NEUTRAL"),
        "fear_greed": round(signal.get("fear_greed", 38.0), 1),
        "momentum_delta": round(signal.get("momentum_delta", 0), 2),
        "btc_dominance_signal": signal.get("btc_dominance_signal", -50),
        "composite": round(signal.get("composite", 0), 2),
        "signal_description": get_signal_desc(signal),
        "prices": {k: round(v, 4) for k, v in prices.items()},
        "positions": positions,
        "twak": {
            "connected": False,
            "server_url": "http://127.0.0.1:3000",
            "wallet_address": "0xc1Ee4085239D86eB55a3BE5Ba0e83b3c3283381A",
            "wallet_address_short": "0xc1Ee...381A",
            "chain": "BSC",
            "balance": "0.0000",
            "btc_price": prices.get("BTC"),
            "bnb_price": prices.get("BNB"),
            "mcp_tools_count": 50
        },
        "agent": agent,
        "mode": "paper",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "last_update": datetime.now().strftime("%H:%M:%S")
    })

@app.route("/api/signal")
def api_signal():
    signal = get_live_signal()
    return jsonify({
        "action": signal.get("action", "NEUTRAL"),
        "fear_greed": round(signal.get("fear_greed", 38.0), 1),
        "momentum_delta": round(signal.get("momentum_delta", 0), 2),
        "btc_dominance_signal": signal.get("btc_dominance_signal", -50),
        "composite": round(signal.get("composite", 0), 2),
        "description": get_signal_desc(signal)
    })

@app.route("/api/prices")
def api_prices():
    return jsonify(get_live_prices())

@app.route("/api/positions")
def api_positions():
    return jsonify(get_paper_positions())

@app.route("/api/agent/status")
def api_agent_status():
    return jsonify(get_agent_status())

@app.route("/api/agent/start", methods=["POST"])
def api_agent_start():
    state = load_state()
    state["running"] = True
    save_state(state)
    return jsonify({"status": "started"})

@app.route("/api/agent/stop", methods=["POST"])
def api_agent_stop():
    state = load_state()
    state["running"] = False
    save_state(state)
    return jsonify({"status": "stopped"})

@app.route("/api/twak/status")
def api_twak_status():
    prices = get_live_prices()
    return jsonify({
        "connected": False,
        "server_url": "http://127.0.0.1:3000",
        "wallet_address": "0xc1Ee4085239D86eB55a3BE5Ba0e83b3c3283381A",
        "wallet_address_short": "0xc1Ee...381A",
        "btc_price": prices.get("BTC"),
        "bnb_price": prices.get("BNB")
    })

@app.route("/api/status")
def api_status():
    return jsonify(load_state())

@app.route("/api/trades")
def api_trades():
    return jsonify(load_state().get("trades", []))

def get_signal_desc(signal):
    action = signal.get("action", "NEUTRAL")
    fg = signal.get("fear_greed", 50)
    if action == "ACCUMULATE":
        return f"Fear level {fg:.0f} — buying the dip."
    elif action == "TAKE_PROFIT":
        return f"Greed level {fg:.0f} — taking profits."
    return f"Neutral zone ({fg:.0f}) — hold and wait."

# Vercel exports 'app' as the WSGI callable
# Do NOT use a handler() wrapper — Vercel wraps app automatically