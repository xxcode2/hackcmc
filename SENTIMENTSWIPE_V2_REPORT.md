# SENTIMENTSWIPE V2 — Hackathon Build Report

## Project Overview

**Name:** SentimentSwipe V2  
**Track:** Track 1 — Autonomous Trading Agents  
**Stack:** CMC Data API + Trust Wallet Agent Kit (TWAK) + BNB AI Agent SDK + BSC  
**Goal:** Build an autonomous agent that reads CMC sentiment signals and executes trades on BSC via TWAK  
**Prize Target:** $10,000 (1st) + $2,000 (Best Use of TWAK) + $2,000 (Best Use of Agent Hub)

---

## The Problem We Solve

Retail crypto traders lose money because:
1. They react emotionally to market swings (FOMO, panic sell)
2. They don't have real-time sentiment data
3. Manual trading is slow — by the time they react, opportunity is gone
4. They don't have systematic risk management

**SentimentSwipe V2** solves this by building an agent that:
- Reads Fear & Greed + Social Sentiment automatically
- Makes data-driven decisions without emotion
- Executes trades in seconds via autonomous signing
- Enforces strict risk guardrails to prevent blowup

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      SENTIMENTSWIPE V2                       │
│                                                             │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────────┐  │
│  │  CMC DATA   │───▶│  AGENT BRAIN │───▶│  TWAK EXECUTOR │  │
│  │  (L1 Stack) │    │  (Python)    │    │  (L2 + L3)     │  │
│  └─────────────┘    └──────────────┘    └────────────────┘  │
│        │                   │                     │          │
│        │                   │                     │          │
│        ▼                   ▼                     ▼          │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────────┐  │
│  │ Fear & Greed│    │  Decision    │    │  Sign + Broadcast│  │
│  │ Social Sent │    │  Engine      │    │  (Local Key)   │  │
│  │ Funding Rate│    │  Risk Manager│    │  Autonomous    │  │
│  │ Price Data  │    │  PositionMgr │    │  x402 Native   │  │
│  └─────────────┘    └──────────────┘    └────────────────┘  │
│                           │                                  │
│                           ▼                                  │
│                    ┌──────────────┐                         │
│                    │  BSC CHAIN   │                         │
│                    │  PancakeSwap │                         │
│                    │  BSC Perps   │                         │
│                    └──────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Layer (CMC API Integration)

### Data Sources Used:

| Source | Endpoint | Purpose |
|--------|----------|---------|
| Fear & Greed | `/public/v2/indicator/{id}` | Market sentiment baseline |
| Social Sentiment | `/public/v2/posts` | KOL chatter, social heat |
| Funding Rates | `/public/v2/futures/{symbol}/funding_rate` | Perp market bias |
| Price Quotes | `/public/v2/quotes/latest` | Entry/exit prices |
| Market Metrics | `/public/v2/market-metrics` | Volatility, volume |

### x402 Integration:
- Pay-per-request for premium data (social posts, KOL signals)
- Agent uses real x402 in trade loop (not cosmetic)
- Budget: ~$0.001 per request

---

## Agent Brain (Decision Engine)

### Core Loop:
```
EVERY CYCLE (every 5 minutes):
  
  1. FETCH DATA
     - Fear & Greed index (0-100)
     - Social sentiment score (-1 to +1)
     - Funding rates (major perp pairs)
     - Price momentum (last 1h, 4h, 24h)
     
  2. CALCULATE SIGNAL SCORE
     - Fear & Greed: weight 40%
     - Social: weight 30%
     - Funding: weight 30%
     - Composite score: -100 to +100
     
  3. DECIDE ACTION
     Signal Score  │ Action
     --------------│----------------
     > +40 (Greed) │ Take profit, reduce exposure
     +20 to +40    │ Hold, slight exposure
     -20 to +20    │ Neutral, minimal position
     -20 to -40    │ Accumulate, increase exposure
     < -40 (Fear)  │ Buy the dip, max safe exposure
     
  4. POSITION SIZING
     - Base position: 10% of portfolio
     - Confidence multiplier: 1.0x to 2.0x based on signal strength
     - Max position per token: 20% of portfolio
     
  5. EXECUTE VIA TWAK
     - Check guardrails (drawdown, stop loss, daily limit)
     - Sign transaction locally
     - Broadcast to BSC
     - Log tx hash
```

### Signal Calculation (Pseudocode):
```python
def calculate_signal():
    fg = get_fear_greed()  # 0-100, normalize to -50 to +50
    social = get_social_sentiment()  # -1 to +1, scale to -50 to +50
    funding = get_funding_rate()  # -0.1% to +0.1%, scale to -50 to +50
    
    raw_score = (fg * 0.4) + (social * 0.3) + (funding * 0.3)
    
    # Apply momentum filter
    prev_score = get_previous_signal()
    momentum = raw_score - prev_score
    
    # If sudden reversal, reduce confidence
    if abs(momentum) > 30:
        raw_score = prev_score + (momentum * 0.5)
    
    return clamp(raw_score, -100, 100)
```

---

## Risk Management (Guardrails)

### Mandatory Rules (Enforced Every Trade):

| Rule | Value | Reason |
|------|-------|--------|
| Max Drawdown | 15% (DISQ @ 30%) | Survival first |
| Stop Loss | 5% per trade | Prevent single-trade blowup |
| Max Position | 20% per token | Diversification |
| Daily Trade Limit | 5 trades/day | Overtrading prevention |
| Eligible Tokens Only | 149 BEP-20 list | Competition rule |
| Min Portfolio Value | $1 | Competition rule |
| x402 Budget | $0.50/day max | Cost control |

### Emergency Kill Switches:
```python
if portfolio_drawdown > 0.30:
    # DISQUALIFIED - emergency exit all positions
    liquidate_all()
    pause_agent()
    notify()
    
if portfolio_value < 1.0:
    # Hour returns = 0% - pause trading
    pause_agent()
    notify()
```

---

## TWAK Integration Depth (Special Prize Scoring)

### TWAK Features Used:

| Feature | Usage in SentimentSwipe | Points |
|---------|------------------------|--------|
| Local Signing | Private key never leaves machine | 20-25 |
| Autonomous Mode | Agent signs txs without manual approve | 20 |
| MCP Integration | `competition_register`, trade actions | 30 |
| x402 Native | Real pay-per-call in trade loop | 10 |
| Multi-chain | BSC primary, fallback awareness | 5 |
| **TOTAL** | | **85-90** |

### TWAK Flow:
```
Agent Decision: "Swap 0.1 BNB → USDT"
        │
        ▼
TWAK MCP Action: twak_swap()
        │
        ▼
Local Sign: Private key signs tx locally
        │
        ▼
Broadcast: Tx sent to BSC
        │
        ▼
Tx Hash: 0xABC123... (logged)
```

### x402 in Trade Loop:
```python
def trade_with_x402():
    # x402 payment for premium social data
    headers = {"x402": "pay 0.001 https://coinmarketcap.com/api/..."}
    social_data = requests.get(cmc_api, headers=headers)
    
    # x402 payment for inference
    headers = {"x402": "pay 0.0005 https://inference.provider/..."}
    signal = model.infer(social_data, headers=headers)
    
    # x402 payment for TWAK signing
    headers = {"x402": "pay 0.0002 https://trustwallet.agent/..."}
    tx_hash = twak.sign_and_send(action, headers=headers)
```

---

## Token Selection (Eligible 149 BEP-20)

### Filtering Criteria:
1. Must be in eligible list (USD1, USDe, BNB, BTC, ETH, etc.)
2. Liquidity > $1M (Slippage control)
3. CMC ranking top 200 (Data reliability)
4. Not stablecoin-only portfolio (Diversification)

### Priority Tokens:
```
TIER 1 (Core):
- BNB (gas + trading pair)
- BTC, ETH (liquidity, trend following)
- USD1, USDe, FDUSD (stable pairs for entries)

TIER 2 (Signals):
- High beta: CAKE, CAKE, TWT (BSC ecosystem)
- Funded: Tokens with positive funding (short bias)
- Sentiment: High social volume tokens

TIER 3 (Opportunistic):
- Dip candidates: Top 50 by market cap with Fear reading <25
- Breakout candidates: Price breaking 24h high with bullish sentiment
```

---

## Handling Losses

### Scenario 1: Small Loss (<5%)
```
Action: Accept loss, log, continue
Reason: Normal variance, strategy survives
Recovery: Next profitable trade
```

### Scenario 2: Medium Loss (5-15%)
```
Action: Reduce position size 50%, review signal
Reason: Possible trend reversal
Recovery: Wait for stronger signal (>40 composite)
```

### Scenario 3: Large Loss (15-30%)
```
Action: Stop new trades, hold existing
Reason: Near drawdown limit
Recovery: Wait for Fear >70 or manual intervention
```

### Scenario 4: Near Disqualification (>30%)
```
Action: EMERGENCY EXIT ALL
Reason: Competition disqualification
Recovery: Liquidate, notify user, pause agent
```

### Loss Recovery Strategy:
```python
def handle_loss(trade_result):
    if trade_result.pnl_pct < -0.05:
        # Small loss - reduce next position
        config.position_size *= 0.75
        log(f"Position reduced to {config.position_size}")
        
    if trade_result.pnl_pct < -0.15:
        # Medium loss - enter "conservation mode"
        config.max_position = 0.10  # Cut in half
        config.signal_threshold *= 1.5  # Only trade strong signals
        notify("Conservation mode activated")
        
    if portfolio_drawdown > 0.25:
        # Near DISQ - emergency
        emergency_exit_all()
        pause_agent()
        notify("EMERGENCY: Agent paused, manual review required")
```

---

## Handling Profits

### Profit Taking Rules:
```python
def handle_profit(trade_result):
    if trade_result.pnl_pct > 0.10:
        # 10%+ gain - take partial profit
        sell_portion(position * 0.5)
        log("Took 50% profit")
        
    if trade_result.pnl_pct > 0.20:
        # 20%+ gain - take most profit
        sell_portion(position * 0.75)
        log("Took 75% profit, trailing stop activated")
        activate_trailing_stop(5%)  # 5% trailing stop
        
    if portfolio_total_return > 0.15:
        # 15%+ overall - lock in some gains
        reduce_exposure(30%)
        log("Portfolio up 15%+, reduced exposure")
```

### Reinvestment Strategy:
```
Total Return  │ Action
--------------│---------------------------
0-10%         │ Reinvest all profits
10-20%        │ Reinvest 75%, take 25%
>20%          │ Reinvest 50%, take 50%
>50%          │ Take 75%, hold 25% as reserve
```

---

## Gas Strategy

### BSC Gas Optimization:
```
Normal conditions:
- Target gas: 5-10 gwei
- Swap gas: ~$0.10-0.20
- Use BNB for gas (cheapest)

High congestion:
- Pause non-essential trades
- Batch transactions if possible
- Increase gas only for urgent exits

Gas budget per day:
- Assume 5 trades × $0.15 = $0.75/day
- Max budget: $2.00/day
- Reserve: $5.00 buffer
```

---

## Dashboard (Monitoring UI)

### Features:
1. **Portfolio Overview**
   - Current value in USD
   - PnL (% and $)
   - Daily change

2. **Signal Monitor**
   - Current Fear & Greed
   - Social sentiment score
   - Composite signal
   - Signal history chart

3. **Trade Log**
   - All executed trades
   - Tx hash (link to BSC scan)
   - Entry/exit prices
   - PnL per trade

4. **Risk Indicators**
   - Current drawdown %
   - Position sizes
   - Guardrail status (green/yellow/red)

### Tech Stack:
- Python + Flask (simple, fast)
- CMC API for data
- Bootstrap for UI
- Hosted locally or simple VPS

---

## Competition Timeline

| Date | Action |
|------|--------|
| June 3-21 | Build window |
| June 22-28 | Live trading week |
| June 29 - July 5 | Judging |
| July 6+ | Winners announced |

### Build Plan:
```
Day 1-2:   Core agent + signal engine
Day 3-4:   TWAK integration + guardrails
Day 5-6:   Testing + paper trading
Day 7-10:  Dashboard + x402 integration
Day 11-14: Testing + refinements
Day 15-18: Live dry run + fixes
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Total Return | >10% (conservative), >20% (target) |
| Max Drawdown | <15% |
| Win Rate | >55% |
| Total Trades | 7+ (minimum for qualify) |
| x402 Usage | Real payments in loop |
| TWAK Integration | Autonomous mode, local signing |

---

## Special Prize Alignment

### Best Use of TWAK:
- [x] Local signing (private key never leaves machine)
- [x] Autonomous mode (agent drives, no manual approval)
- [x] MCP integration (competition_register, trade actions)
- [x] x402 native (real pay-per-call in trade loop)

### Best Use of Agent Hub:
- [x] CMC Fear & Greed (indicator endpoint)
- [x] Social sentiment (posts + KOL data)
- [x] Funding rates (futures endpoint)
- [x] x402 for data calls

### Differentiation:
- Not just another arbitrage bot
- Novel sentiment → execution loop
- Real utility for retail traders
- Self-custody integrity maintained

---

## Team & Roles

- **Developer:** Hermes Agent (AI)
- **Strategy:** Sentiment-driven DCA with adaptive sizing
- **Risk:** User-defined guardrails (max drawdown, stop loss)
- **Execution:** TWAK autonomous mode

---

## Risk Disclaimer

**THIS IS REAL TRADING WITH REAL MONEY.**

- Agent can and will lose money
- Past performance does not guarantee future results
- User is responsible for final decision to deploy agent
- Only trade with capital you can afford to lose