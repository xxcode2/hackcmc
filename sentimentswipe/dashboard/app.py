"""
SENTIMENTSWIPE V2 - Flask Dashboard
Simple web UI for monitoring the agent
"""

import os
import json
from flask import Flask, render_template, jsonify, request
from datetime import datetime

app = Flask(__name__)

# Global state (in production, use Redis or similar)
STATE_FILE = "logs/agent_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
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
    os.makedirs("logs", exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/api/status")
def api_status():
    state = load_state()
    return jsonify(state)

@app.route("/api/trades")
def api_trades():
    state = load_state()
    return jsonify(state.get("trades", []))

@app.route("/api/signal")
def api_signal():
    state = load_state()
    return jsonify(state.get("last_signal", {}))

@app.route("/api/start", methods=["POST"])
def api_start():
    state = load_state()
    state["running"] = True
    save_state(state)
    return jsonify({"status": "started"})

@app.route("/api/stop", methods=["POST"])
def api_stop():
    state = load_state()
    state["running"] = False
    save_state(state)
    return jsonify({"status": "stopped"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)