# SENTIMENTSWIPE V2 🤖

**Autonomous Sentiment-Driven Trading Agent for BNB Chain**

Built for: [BNB Hack: CMC Agent Hackathon 2026](https://coinmarketcap.com/api/hackathon/)  
Track: Track 1 — Autonomous Trading Agents  
Stack: CoinMarketCap API + Trust Wallet Agent Kit + BNB AI Agent SDK

---

## What It Does

SentimentSwipe V2 is an autonomous trading agent that:

1. **Reads market sentiment** from CMC (Fear & Greed, social data, funding rates)
2. **Makes data-driven decisions** without emotion
3. **Executes trades autonomously** via Trust Wallet Agent Kit
4. **Enforces strict risk guardrails** to prevent blowup

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  CMC Data (Fear & Greed, Social, Funding)                   │
│            ↓                                                 │
│  Signal Engine → Decision (BUY/SELL/HOLD)                   │
│            ↓                                                 │
│  Risk Manager (drawdown, position size, guardrails)         │
│            ↓                                                 │
│  TWAK Executor → Autonomous Swap on PancakeSwap/BSC        │
└─────────────────────────────────────────────────────────────┘
```

## Signal Logic

| Composite Signal | Action |
|-----------------|--------|
| > +40 (Greed) | Take profit, reduce exposure |
| +20 to +40 | Slight bullish, hold |
| -20 to +20 | Neutral, minimal position |
| -20 to -40 | Accumulate, increase exposure |
| < -40 (Fear) | Buy the dip, max safe exposure |

## Risk Management

- **Max Drawdown:** 15% (auto-conservation) | 30% = DISQ
- **Stop Loss:** 5% per trade
- **Take Profit:** 10% with trailing stop
- **Position Size:** 10% base (up to 20% max)
- **Daily Trades:** Max 5/day

## Project Structure

```
sentimentswipe/
├── agent.py                 # Main trading agent
├── requirements.txt         # Python dependencies
├── config/
│   └── config.py           # All configuration
├── signals/
│   └── signal_engine.py    # CMC data fetcher + signal calculator
├── executor/
│   └── twak_executor.py    # TWAK integration for autonomous execution
├── risk_manager/
│   └── risk_engine.py      # Risk controls, position management
└── dashboard/
    ├── app.py              # Flask monitoring dashboard
    └── templates/
        └── dashboard.html  # Web UI
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file:

```env
CMC_API_KEY=your_coinmarketcap_api_key
AGENT_PRIVATE_KEY=your_agent_wallet_private_key
```

Get CMC API key: https://coinmarketcap.com/api/

### 3. Generate Agent Wallet

```bash
# Use TWAK CLI to generate new wallet
twak generate --chain 56

# SAVE THE PRIVATE KEY - you need it for .env
```

### 4. Register for Competition (Track 1)

```bash
python agent.py --register
```

This registers your agent wallet on-chain via the competition contract.

### 5. Run the Agent

```bash
# Paper trading (outside competition window)
python agent.py --capital 100

# Run dashboard (separate terminal)
cd dashboard && python app.py
```

## Competition Rules

- **Dates:** June 22-28, 2026 (live trading week)
- **Min Trades:** 7 (1/day minimum)
- **Eligible Tokens:** 149 BEP-20 tokens (full list in config.py)
- **Risk Gate:** Max 30% drawdown = disqualification
- **Min Portfolio:** Must maintain >$1 balance

## x402 Integration

SentimentSwipe V2 uses x402 for pay-per-request in the trade loop:

```python
# Example: Pay for premium social data
headers = {"x402": "pay 0.001 https://coinmarketcap.com/api/..."}
data = requests.get(cmc_api, headers=headers)
```

This demonstrates native x402 usage for special prize criteria.

## TWAK Integration Features

| Feature | Status |
|---------|--------|
| Local Signing | ✅ Private key never leaves machine |
| Autonomous Mode | ✅ Agent signs without manual approval |
| MCP Actions | ✅ `competition_register`, `swap` |
| x402 Native | ✅ Real payments in trade loop |
| BSC/56 Chain | ✅ Primary chain |

## Special Prize Alignment

- **Best Use of TWAK:** Full self-custody, autonomous mode, x402 native
- **Best Use of Agent Hub:** CMC Fear & Greed, social, funding, x402
- **Best Use of BNB SDK:** PancakeSwap integration, BSC execution

## Testing

```bash
# Test signal engine
python -c "from signals.signal_engine import SignalEngine; ..."

# Test risk manager
python -c "from risk_manager.risk_engine import RiskManager; ..."

# Paper trade cycle
python agent.py --capital 100
```

## Dashboard

Start the monitoring dashboard:

```bash
cd dashboard
python app.py
```

Open http://localhost:5000 to monitor:
- Portfolio value + P&L
- Current signal + components
- Open positions
- Trade history

## Legal

**THIS IS REAL TRADING WITH REAL MONEY.**

- Past performance does not guarantee future results
- Only trade with capital you can afford to lose
- The agent can and will lose money

## License

MIT

---

Built with ❤️ for the BNB Hack: CMC Agent Hackathon 2026