"""
SENTIMENTSWIPE V2 - Configuration
All configurable parameters in one place.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# === API KEYS ===
CMC_API_KEY="e234f83950e44af38f101284ec4692c1"  # CoinMarketCap API key

# === AGENT WALLET ===
AGENT_PRIVATE_KEY = os.getenv("AGENT_PRIVATE_KEY", "")
# Generate fresh key for competition. NEVER share this.

# === TRADING PAIRS (BSC/PancakeSwap) ===
# Primary trading pairs - these are eligible tokens
PRIMARY_TOKENS = ["BNB", "BTC", "ETH", "USDT", "USDC", "FDUSD", "USD1", "USDe"]
TRADING_PAIR = "USDT"  # Quote currency for most trades

# === SIGNAL WEIGHTS ===
WEIGHT_FEAR_GREED = 0.40
WEIGHT_SOCIAL = 0.30
WEIGHT_FUNDING = 0.30

# === SIGNAL THRESHOLDS ===
SIGNAL_BULLISH_THRESHOLD = 40   # >40 = greedy, take profit
SIGNAL_BEARISH_THRESHOLD = -40  # <-40 = fear, buy dip
SIGNAL_NEUTRAL_UPPER = 20       # 20-40 = slight bullish
SIGNAL_NEUTRAL_LOWER = -20      # -20 to 20 = neutral

# === POSITION SIZING ===
BASE_POSITION_PCT = 0.10        # 10% of portfolio per trade
MAX_POSITION_PCT = 0.20         # Max 20% per token
MIN_POSITION_VALUE = 5.0        # Min $5 per position
MAX_POSITION_VALUE = 200.0      # Max $200 per position

# === RISK MANAGEMENT ===
MAX_DRAWDOWN = 0.15             # 15% drawdown = conservation mode
DISQUALIFICATION_DRAWDOWN = 0.30  # 30% = emergency exit + pause
STOP_LOSS_PCT = 0.05            # 5% stop loss per trade
TAKE_PROFIT_PCT = 0.10          # 10% take profit target
TRAILING_STOP_PCT = 0.05        # 5% trailing stop after 20% gain

DAILY_TRADE_LIMIT = 5           # Max 5 trades per day
MIN_TRADES_PER_WEEK = 7         # Competition minimum

# === GAS STRATEGY ===
MAX_GAS_PRICE_GWEI = 20
SWAP_GAS_ESTIMATE_USD = 0.15
DAILY_GAS_BUDGET = 2.0

# === CYCLE TIMING ===
CYCLE_INTERVAL_MINUTES = 5      # Check signals every 5 minutes
SIGNAL_HISTORY_WINDOW = 24      # Store 24 hours of signal history

# === x402 SETTINGS ===
X402_BUDGET_DAILY = 0.50        # Max $0.50/day for x402 calls

# === COMPETITION ===
COMPETITION_START = "2026-06-22T00:00:00Z"
COMPETITION_END = "2026-06-28T23:59:59Z"
COMPETITION_CONTRACT = "0x212c61b9b72c95d95bf29cf032f5e5635629aed5"
ELIGIBLE_TOKENS = [
    "ETH", "USDT", "USDC", "XRP", "TRX", "DOGE", "ADA", "LINK", "BCH", "DAI",
    "TON", "USD1", "USDe", "M", "LTC", "AVAX", "SHIB", "XAUt", "WLFI", "H",
    "DOT", "UNI", "ASTER", "DEXE", "USDD", "ETC", "AAVE", "ATOM", "U", "STABLE",
    "FIL", "INJ", "币安人生", "NIGHT", "FET", "TUSD", "BONK", "PENGU", "CAKE",
    "SIREN", "LUNC", "ZRO", "KITE", "FDUSD", "BEAT", "PIEVERSE", "BTT", "NFT",
    "EDGE", "FLOKI", "LDO", "B", "FF", "PENDLE", "NEX", "STG", "AXS", "TWT",
    "HOME", "RAY", "COMP", "GWEI", "XCN", "GENIUS", "XPL", "BAT", "SKYAI", "APE",
    "IP", "SFP", "TAG", "NXPC", "AB", "SAHARA", "1INCH", "CHEEMS", "BANANAS31",
    "RIVER", "MYX", "RAVE", "SNX", "FORM", "LAB", "HTX", "USDf", "CTM", "BDX",
    "SLX", "UB", "DUCKY", "FRAX", "BILL", "WFI", "KOGE", "ALE", "FRXUSD", "USDF",
    "GOMINING", "VCNT", "GUA", "DUSD", "SMILEK", "0G", "BEAM", "MY", "SOON",
    "REAL", "Q", "AIOZ", "ZIG", "YFI", "TAC", "lisUSD", "CYS", "ZAMA", "TRIA",
    "HUMA", "PLUME", "ZIL", "XPR", "ZETA", "BabyDoge", "NILA", "ROSE", "VELO",
    "UAI", "BRETT", "OPEN", "BSB", "TOSHI", "BAS", "ACH", "AXL", "LUR", "ELF",
    "KAVA", "APR", "IRYS", "EURI", "XUSD", "BARD", "DUSK", "SUSHI", "PEAQ",
    "COAI", "BDCA", "XAUM", "BNB"
]

# === TWAK SETTINGS ===
TWAK_MCP_ENABLED = True
TWAK_AUTONOMOUS_MODE = True

# === LOGGING ===
LOG_FILE = "logs/sentimentswipe.log"
LOG_LEVEL = "INFO"