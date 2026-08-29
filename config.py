"""Central config. Secrets come from ENV (never commit them)."""
import os

# Coins to cover (base symbols). Binance=+USDT, Coinbase=+-USD, OKX=+-USDT.
COINS = os.environ.get("COINS", "BTC,ETH,SOL,BNB,XRP,DOGE").split(",")

# Discord webhook (set as a GitHub Actions secret DISCORD_WEBHOOK_URL)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

# Network
HTTP_TIMEOUT = 12
RETRIES = 3

# Volatility / regime params
HAR_LOOKBACKS_H = (24, 72, 168)     # day / 3-day / week (hourly bars)
HAR_HISTORY_H   = 1000              # hours of history to fit HAR (~42 days)
FWD_H           = 24               # forecast horizon (next 24h)
REGIME_WIN_H    = 24 * 60          # ~60 days for regime percentile
STORM_PCTILE    = 70
CALM_PCTILE     = 30
EXPANSION_EMA_H = 48
EXPANSION_MULT  = 1.15

# Order-flow / derivatives
FUNDING_EXTREME = 0.0005            # 0.05% per 8h ~ elevated
OI_BUILD_PCT    = 5.0               # % 24h OI change flagged as build/unwind
WHALE_USD       = 25_000           # trade >= this = "whale" print

# Levels / liquidation model
VP_BINS         = 50               # volume-profile price bins
VP_WINDOW_H     = 168             # ~1 week for the profile
LEVERAGE_TIERS  = (25, 50, 100)    # common perp leverage -> estimated liq magnets

# Report tier: "free" (1-liner), "retail" (plain+key metrics), "pro" (everything)
TIER = os.environ.get("TIER", "pro").lower()

BRAND = "📊 Crypto Vol & Risk Intel"
DISCLAIMER = "Analytics, not financial advice. We forecast RISK (volatility/regime), never direction. DYOR."
