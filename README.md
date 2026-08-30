# 📊 Crypto Vol & Risk Intel

Automated crypto **volatility, risk and cost intelligence** for 5–6 major coins, posted to Discord every 30 minutes.

**Not signals.** We forecast the one thing that is actually predictable — **risk (volatility, regime, expected range)** — then we do the thing nobody else does: **check whether that range is even big enough to pay for the trade.** We never sell "buy/sell direction," because direction is a coin flip net of cost.

## What each report contains

- **Volatility forecast at four horizons** — 30m / 1h / 4h / 24h, each a 1σ expected move, from a HAR model on ~2 years of history.
- **A cost gate on every horizon.** Expected move ÷ round-trip cost. Below 3× it says `DEAD` and tells you to stand aside. This is the headline, because it is the only certain number in the report.
- **Regime** — CALM / NORMAL / STORM (percentile) **anchored to absolute cost**, so "top of a dead range" can't masquerade as a storm.
- **The clock** — measured hour-of-day volatility profile (BTC ~2.2×, ETH ~2.0×, SOL ~1.8× between the busiest and deadest hour).
- **Order flow** — taker CVD lean at 1h/4h/24h, each as a **percentile of its own 30-day history**.
- **Factor decomposition** — beta and R² to BTC, plus idiosyncratic residual vol, so you know when a coin is actually doing something of its own versus repeating BTC with extra fees.
- **Derivatives** — funding, open interest, long/short, top-trader positioning.
- **Track record** — every forecast, at every horizon, git-committed to `data/forecasts.csv`.

## The model is validated, and you can check it yourself

```bash
python validate.py --coins BTC,ETH,SOL
```

Walk-forward, expanding-window, non-overlapping evaluation, with a `fwd`-bar gap so the rolling forward-sum target cannot leak into the fit. Measured 2026-08-30 on 2y of hourly + 69d of 5m bars:

| horizon | mean OOS R² | range | beats naive |
|---|---|---|---|
| 30m | **+0.396** | 0.331 – 0.443 | 3/3 |
| 1h  | **+0.435** | 0.341 – 0.483 | 3/3 |
| 4h  | **+0.449** | 0.364 – 0.521 | 3/3 |
| 24h | **+0.318** | 0.298 – 0.339 | 3/3 |

The R² printed in every report is **that** number — a walk-forward out-of-sample R², not an in-sample fit.

## The uncomfortable part, published on purpose

Round-trip cost as a share of the mean absolute move (Binance spot taker 0.15%, 2y):

| horizon | BTC | ETH | SOL |
|---|---|---|---|
| 30m | **68%** | 46% | 38% |
| 1h  | 48% | 33% | 27% |
| 4h  | 24% | 16% | 13% |
| 24h | 9%  | 6%  | 5%  |

On a normal day, **30-minute BTC trading on taker fees is a fee donation** — the forecast is good, the trade is not. The product says so out loud rather than selling you a range you can't monetise. Use maker/limit fills or a longer horizon.

## Quick start

```bash
pip install -r requirements.txt
python main.py --dry          # console only, no Discord
```

```bash
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..." python main.py
```

## Automated (GitHub Actions)

Runs every 30 min via `.github/workflows/run.yml`; a separate daily job re-runs `validate.py` so the OOS claim can't quietly go stale. Set repo secret **`DISCORD_WEBHOOK_URL`**. Use a **public** repo (unlimited Actions minutes) or a VPS.

See **[CONTEXT.md](CONTEXT.md)** for architecture and onboarding, **[BUILDLOG.md](BUILDLOG.md)** for what was fixed and why.

_Analytics, not financial advice._
