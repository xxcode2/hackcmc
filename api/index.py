"""
Vercel Serverless Flask - SENTIMENTSWIPE Dashboard
Route: / -> dashboard, /api/* -> JSON endpoints
"""

import os
import sys
import json

# Add sentimentswipe to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sentimentswipe'))

from flask import Flask, render_template, jsonify, request, Response
from datetime import datetime

app = Flask(__name__, template_folder='../sentimentswipe/dashboard/templates')

STATE_FILE = os.path.join(os.path.dirname(__file__), '..', 'sentimentswipe', 'logs', 'agent_state.json')

def load_state():
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
        "last_signal": {"fear_greed": 50, "composite": 0, "action": "NEUTRAL"},
        "running": False
    }

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/api/status")
def api_status():
    return jsonify(load_state())

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
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    return jsonify({"status": "started"})

@app.route("/api/stop", methods=["POST"])
def api_stop():
    state = load_state()
    state["running"] = False
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    return jsonify({"status": "stopped"})

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found", "routes": ["/", "/api/status", "/api/trades", "/api/signal"]}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Server error"}), 500