# SENTIMENTSWIPE V2 🤖

**Autonomous Sentiment-Driven Trading Agent for BNB Chain**

Built for: [BNB Hack: CMC Agent Hackathon 2026](https://coinmarketcap.com/api/hackathon/)  
Track: Track 1 — Autonomous Trading Agents  
Prize Pool: $36,000 | Special Prizes: $2,000 each  
Stack: CoinMarketCap API + Trust Wallet Agent Kit (TWAK) + BNB AI Agent SDK + BSC

---

## What It Does

SentimentSwipe V2 is an autonomous trading agent that:
1. **Reads market sentiment** from CMC (Fear & Greed proxy, price momentum, BTC dominance)
2. **Makes data-driven decisions** without emotion
3. **Executes trades autonomously** via TWAK or direct Web3/PancakeSwap
4. **Enforces strict risk guardrails** to prevent blowup

```
CMC Data (Fear & Greed, Momentum, BTC Dominance)
        ↓
Signal Engine → Composite Score → Action (BUY/SELL/HOLD)
        ↓
Risk Manager (drawdown, position size, stop loss)
        ↓
TWAK/Web3 Executor → PancakeSwap on BSC → tx broadcast
```

---

## Signal Logic

| Composite | Action | Meaning |
|-----------|--------|---------|
| > +40 | TAKE_PROFIT | Greed — reduce exposure |
| +20 to +40 | SLIGHT_BULLISH | Slight bullish — hold |
| -20 to +20 | NEUTRAL | No strong signal |
| -20 to -40 | ACCUMULATE | Fear — increase exposure |
| < -40 | BUY_DIP | Extreme fear — buy the dip |

Signal = Fear&Greed(40%) + Momentum(35%) + BTC Dominance(25%)

---

## Risk Management

| Rule | Value | Purpose |
|------|-------|---------|
| Max Drawdown | 15% → conservation, 30% → DISQ | Survival |
| Stop Loss | 5% per trade | Single-trade protection |
| Take Profit | 10% + 5% trailing stop | Lock gains |
| Position Size | 10% base (max 20%) | Diversification |
| Daily Trades | Max 5/day | Prevent overtrading |
| Token Selection | 149 eligible BEP-20 only | Competition rules |

---

## Project Structure

```
hackcmc/
├── SENTIMENTSWIPE_V2_REPORT.md    # Full architecture doc
├── run.sh                         # Quick start script
├── sentimentswipe/
│   ├── agent.py                   # Main agent + CLI
│   ├── requirements.txt           # Dependencies
│   ├── config/
│   │   └── config.py             # All settings
│   ├── signals/
│   │   └── signal_engine.py      # CMC data + signal calculation
│   ├── executor/
│   │   ├── twak_executor.py      # TWAK CLI integration
│   │   └── web3_executor.py      # Web3/PancakeSwap fallback
│   ├── risk_manager/
│   │   └── risk_engine.py        # Risk controls
│   └── dashboard/
│       ├── app.py                # Flask monitoring API
│       └── templates/
│           └── dashboard.html    # Web UI
```

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r sentimentswipe/requirements.txt
```

### 2. Test Signal Engine (No Wallet Needed)

```bash
cd sentimentswipe
python -c "from signals.signal_engine import SignalEngine; from config.config import CMC_API_KEY; se = SignalEngine(CMC_API_KEY); print(se.get_signal_summary())"
```

### 3. Run Paper Trading

```bash
python agent.py --paper --once          # One cycle test
python agent.py --paper --capital 200   # Paper trade $200
```

Or use the run script:
```bash
./run.sh paper 100
./run.sh test
```

### 4. Setup Real Trading

```bash
# Generate wallet
# Save the 64-char hex private key (no 0x)

# Set private key
export AGENT_PRIVATE_KEY="<your_hex_key>"
# or
python agent.py --key <your_hex_key> --capital 100
```

### 5. Register for Competition (Track 1)

```bash
python agent.py --key <PRIVATE_KEY> --register
```

### 6. Dashboard

```bash
cd dashboard && python app.py
# Open http://localhost:5000
```

---

## Competition Details

| Item | Detail |
|------|--------|
| Dates | Build: June 3-21, 2026 \| Trading: June 22-28, 2026 |
| Tracks | Track 1: Autonomous Agents ($24k) \| Track 2: Strategy Skills ($6k) |
| Special Prizes | Best TWAK, Best Agent Hub, Best BNB SDK ($2k each) |
| Registration | On-chain via `twak compete register` or MCP |
| Contract | `0x212c61b9b72c95d95bf29cf032f5e5635629aed5` (BSC) |
| Min Trades | 7 (1/day during trading week) |
| Disqualification | >30% drawdown or portfolio <$1 |
| Eligible Tokens | 149 BEP-20 tokens (list in config.py) |

---

## TWAK Integration (Special Prize Criteria)

SentimentSwipe V2 uses TWAK for:
- **Local Signing**: Private key never leaves machine
- **Autonomous Mode**: Agent signs txs without manual approval
- **MCP Integration**: `competition_register`, `swap` actions
- **x402 Native**: Pay-per-request in trade loop

If TWAK is not installed, falls back to direct Web3/PancakeSwap.

---

## How to Win

### For $10,000 (Track 1 First Place):
1. Highest return % without hitting 30% drawdown
2. Use ALL 3 stack layers (CMC + TWAK + BNB SDK)
3. Show clean self-custody + autonomous execution
4. Demonstrate x402 in real trade loop

### For $2,000 Special (Best TWAK):
1. Use TWAK as ONLY execution layer (not just bolted on)
2. Show autonomous mode — agent drives, no manual signing
3. Demonstrate x402 for data/inference payments
4. Clean self-custody throughout (local key, no custodial)

### Differentiation Points:
- Not just another arbitrage bot
- Novel sentiment → execution loop
- Real utility for retail traders
- Self-custody integrity maintained

---

## Technical Notes

- **BSC RPC**: Uses `bsc.publicnode.com` (works with SSL interception)
- **CMC API**: v1 endpoints (`/v1/cryptocurrency/quotes/latest`, `/v1/global-metrics/`)
- **Fear & Greed**: Derived from market cap change + BTC dominance + volume ratio
- **Paper Trading**: Simulated trades without real wallet
- **Gas**: BSC ~$0.05-0.20 per swap; estimated $2-5/day total

---

## Disclaimer

**REAL TRADING WITH REAL MONEY.**
- Agent can and will lose money
- Past performance does not guarantee future results
- Only trade with capital you can afford to lose
- User is responsible for final deployment decision

---

Built for BNB Hack: CMC Agent Hackathon 2026  
GitHub: https://github.com/xxcode2/hackcmc