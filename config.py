"""Central config. Secrets come from ENV (never commit them)."""
import os

# Coins to cover (base symbols). Binance=+USDT, Coinbase=+-USD, OKX=+-USDT.
COINS = os.environ.get("COINS", "BTC,ETH,SOL,BNB,XRP,DOGE").split(",")

# The market factor every other coin is measured against (beta + residual).
FACTOR_COIN = os.environ.get("FACTOR_COIN", "BTC")

# Discord webhook (set as a GitHub Actions secret DISCORD_WEBHOOK_URL)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

# Optional: Coinglass API key (free tier) for REAL aggregated liquidations across
# 30+ exchanges. Without it we show NO liquidation levels at all (we do not
# fabricate them -- see src/levels.py).
COINGLASS_API_KEY = os.environ.get("COINGLASS_API_KEY", "").strip()

# Optional: OpenRouter for AI easy-language explanations (use a FREE model).
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL   = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

# Network
HTTP_TIMEOUT = 12
RETRIES = 3

# ---------------------------------------------------------------- history
# The HAR model needs YEARS, not weeks. Fitting on 42 days produced a NEGATIVE
# out-of-sample R2 (measured 2026-08-30); 2 years produces +0.21..+0.26.
# These are the real knobs now -- they are actually read by exchanges.klines().
HISTORY_1H_BARS = int(os.environ.get("HISTORY_1H_BARS", 17280))   # ~2 years hourly
HISTORY_5M_BARS = int(os.environ.get("HISTORY_5M_BARS", 20000))   # ~70 days of 5m
CACHE_DIR       = os.environ.get("CACHE_DIR", "data/cache")
CACHE_TTL_S     = int(os.environ.get("CACHE_TTL_S", 1500))        # 25 min

# ---------------------------------------------------------------- horizons
# Measured OOS R2 (walk-forward, non-overlapping eval, 2026-08-30):
#   30m 0.26-0.38 | 1h 0.31-0.44 | 4h 0.25-0.42 | 24h 0.21-0.26
# 1h is BOTH the most skilful horizon and the shortest one that can clear costs
# on the higher-vol coins, so it is the headline.
HORIZONS = (
    # key,  bar interval, bars ahead, label
    ("m30", "5m", 6,  "30m"),
    ("h1",  "5m", 12, "1h"),
    ("h4",  "5m", 48, "4h"),
    ("h24", "1h", 24, "24h"),
)
PRIMARY_HORIZON = os.environ.get("PRIMARY_HORIZON", "h1")

HAR_LOOKBACKS_1H = (24, 72, 168)      # day / 3-day / week   (hourly bars)
HAR_LOOKBACKS_5M = (12, 72, 288)      # 1h / 6h / 24h        (5-minute bars)
OOS_FRACTION     = 0.5                # last half of history is the walk-forward test
OOS_REFIT_EVERY  = 50                 # refit cadence inside the walk-forward

# ---------------------------------------------------------------- regime
REGIME_WIN_H    = 24 * 60          # ~60 days for the regime percentile
STORM_PCTILE    = 70
CALM_PCTILE     = 30
EXPANSION_EMA_H = 48
EXPANSION_MULT  = 1.15
# Absolute anchor: a percentile alone is meaningless in a dead month. STORM also
# has to clear this many round-trip costs of expected movement.
STORM_MIN_COST_MULT = 8.0

# ---------------------------------------------------------------- cost model
# Binance spot TAKER, no BNB discount, both sides. Override per venue via ENV.
# Measured cost-as-share-of-mean-move (2y): BTC 30m 68%, 1h 48%, 4h 24%.
# This is the gate that decides whether a horizon is tradeable at all.
FEE_TAKER_BPS   = float(os.environ.get("FEE_TAKER_BPS", 7.5))   # per side, bps
FEE_MAKER_BPS   = float(os.environ.get("FEE_MAKER_BPS", 2.0))   # per side, bps
SLIP_BPS        = float(os.environ.get("SLIP_BPS", 1.0))        # per side, bps
EXEC_STYLE      = os.environ.get("EXEC_STYLE", "taker").lower() # taker | maker
# Expected move must be at least this multiple of round-trip cost to be worth it.
COST_MULT_GO    = 5.0
COST_MULT_MARGINAL = 3.0

# ---------------------------------------------------------------- order flow
# A real window, not 143 seconds. Built from 1m klines' taker-buy quote volume.
FLOW_WINDOW_M   = 60               # rolling window for the live CVD read
FLOW_PCTILE_D   = 30               # normalise every flow metric to its 30-day percentile
FUNDING_EXTREME = 0.0005           # 0.05% per 8h ~ elevated
OI_BUILD_PCT    = 5.0              # % 24h OI change flagged as build/unwind
# "Whale" print threshold. Only ever applied to the last ~2 min of tape, so this
# is a tape-texture read, never positioning -- orderflow.whale_retail says so.
WHALE_USD_DEFAULT = 25_000

# ---------------------------------------------------------------- levels
VP_BINS         = 50               # volume-profile price bins
VP_WINDOW_H     = 168              # ~1 week for the profile

# ---------------------------------------------------------------- seasonality
SEASON_MIN_DAYS = 30               # need this much history before trusting the hour profile

# Report tier: "free" (1-liner), "retail" (plain+key metrics), "pro" (everything)
TIER = os.environ.get("TIER", "pro").lower()

BRAND = "📊 Crypto Vol & Risk Intel"
DISCLAIMER = ("Analytics, not financial advice. We forecast RISK (volatility/regime/cost), "
              "never direction. DYOR.")
