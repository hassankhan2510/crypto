# 📊 Crypto Vol & Risk Intel

Automated crypto **volatility & risk intelligence** for 5–6 major coins, posted to Discord every 30 minutes.

**Not signals.** We forecast the one thing that is actually predictable — **risk (volatility, regime, expected range)** — plus real order-flow and derivatives context, with an honest plain-English verdict. We never sell "buy/sell direction," because direction is a coin flip net of cost (proven across our own research + published papers).

## What each report contains
- **Volatility forecast (HAR model):** expected ±% move & price range over the next 24h, validated out-of-sample.
- **Regime:** CALM / NORMAL / STORM (percentile) + EXPANDING/CONTRACTING.
- **Order flow:** real taker CVD (aggressor buyers vs sellers) + whale-vs-retail split.
- **Derivatives:** funding rate (crowding), open-interest change, long/short ratio.
- **Verdict:** risk regime, squeeze warnings, "stand aside" calls — plain English.
- **Track record:** every forecast is git-committed to `data/forecasts.csv` (tamper-evident).

## Quick start
```bash
pip install -r requirements.txt
python main.py --dry          # console only, no Discord
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..." python main.py   # post
```

## Automated (GitHub Actions)
Runs every 30 min via `.github/workflows/run.yml`. Set repo secret **`DISCORD_WEBHOOK_URL`** (Settings → Secrets and variables → Actions). Use a **public** repo (unlimited Actions minutes) or a VPS.

See **[CONTEXT.md](CONTEXT.md)** for full architecture, onboarding, and how to extend.

_Analytics, not financial advice._
