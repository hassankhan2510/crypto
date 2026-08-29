# CONTEXT.md — Crypto Vol & Risk Intel (full project brief)

> Read this first. It's the single source of truth for this repo: what it is, how it
> works, how to run it, how to deploy it, and how a **new developer** can get productive
> and push changes **without needing the owner's personal accounts**.

---

## 1. What this is (the product)

An automated **crypto volatility & risk intelligence** service. Every 30 minutes a job pulls
free multi-exchange data for 5–6 major coins, computes a validated volatility forecast +
order-flow + derivatives context, writes an honest plain-English verdict, posts it to a
**Discord** channel, and logs every forecast to a git-committed file (the track record).

**Positioning (important — this is the whole moat):**
- We sell **validated RISK intelligence**, not direction signals.
- Direction (up/down) is *not* predictable net of cost — proven across ~25 experiments and
  two written papers. Volatility (move *size*) **is** predictable (HAR, OOS R² 0.11–0.43).
- So we forecast expected range / regime / expansion, show real order-flow & positioning
  context, and give a risk verdict. We **never** say "buy" or "sell."
- Differentiator vs Buildix ($9/mo) / Coinglass ($40/mo): they show *current* metrics for
  scalpers; we give a *validated forward vol forecast + honest verdict + tamper-proof track
  record*, aimed at risk-aware traders and non-trading allocators.

---

## 2. Repository

- **URL:** https://github.com/hassankhan2510/crypto.git
- **Default branch:** `main`
- **Secrets (never committed):** `DISCORD_WEBHOOK_URL` — set as a GitHub Actions secret.

---

## 3. Folder structure

```
cryptointel/
  main.py                 # entry point: pull → compute → report → log → post
  config.py               # coins, thresholds, params; reads secrets from ENV
  requirements.txt        # requests, pandas, numpy
  README.md               # short public overview
  CONTEXT.md              # this file
  .gitignore
  .github/workflows/
    run.yml               # GitHub Actions cron (every 30 min) + auto-commit log
  src/
    http.py               # resilient HTTP GET (retries/timeout)
    exchanges.py          # free multi-exchange data (Binance spot+futures, Coinbase, OKX)
    volatility.py         # HAR volatility forecast + regime + expansion (the differentiator)
    orderflow.py          # taker CVD + whale-vs-retail split
    synthesize.py         # combines everything → per-coin report + honest verdict
    discord_post.py       # rich-embed Discord webhook poster (no-op if no webhook)
    track.py              # appends every forecast to data/forecasts.csv (track record)
  data/
    forecasts.csv         # immutable, git-committed forecast log (created on first run)
```

---

## 4. How it works (pipeline)

1. **exchanges.py** pulls, per coin (all free, no API key):
   - Binance spot 1h klines (OHLCV + real taker-buy volume = aggressor flow), 24h ticker, aggTrades.
   - Binance futures: funding rate, open-interest history, global long/short ratio.
   - Coinbase + OKX last price (cross-exchange agreement / spread).
2. **volatility.py** fits a HAR model (RV over 24h/72h/168h → next-24h realized vol) and
   returns expected ±% move, price range, regime percentile, expansion state, confidence.
3. **orderflow.py** computes taker CVD lean (4h/24h) and whale-vs-retail net flow.
4. **synthesize.py** merges vol + flow + derivatives into a report dict and an honest verdict
   (risk regime, squeeze warnings, stand-aside calls). No buy/sell.
5. **main.py** prints to console, **track.py** logs the forecast, **discord_post.py** posts embeds.

---

## 5. Run it locally

```bash
git clone https://github.com/hassankhan2510/crypto.git
cd crypto            # (or cryptointel/ if nested)
pip install -r requirements.txt

# console only, never posts:
python main.py --dry

# choose coins:
COINS="BTC,ETH,SOL,BNB,XRP,DOGE" python main.py --dry

# post to Discord:
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/XXXX/YYYY" python main.py
```
Windows PowerShell: set env with `$env:DISCORD_WEBHOOK_URL="..."` then `python main.py`.

---

## 6. Deploy (automated, every 30 min)

Handled by `.github/workflows/run.yml`:
- Cron `*/30 * * * *` (UTC) + manual `workflow_dispatch`.
- Installs deps, runs `main.py`, then commits `data/forecasts.csv` back to the repo.
- **Set the secret:** repo → **Settings → Secrets and variables → Actions → New repository
  secret** → name `DISCORD_WEBHOOK_URL`, value = your Discord webhook URL.
- **Minutes:** use a **public** repo (Actions minutes are unlimited) or a $5 VPS + cron.
  A private repo's free 2,000 min/mo will not cover a 30-min cron.

### Get a Discord webhook
Discord server → a channel → Edit Channel → Integrations → Webhooks → New Webhook → Copy URL.
Put that URL in the GitHub secret above (do **not** paste it into code).

---

## 7. Onboarding a NEW developer (no owner credentials needed)

A new dev uses **their own** GitHub account — you never share your password/token.

1. Owner: add them as a collaborator (repo → Settings → Collaborators) **or** they fork the repo.
2. Dev clones with their own auth:
   ```bash
   git clone https://github.com/hassankhan2510/crypto.git
   cd crypto
   pip install -r requirements.txt
   python main.py --dry        # verify it runs
   ```
3. Dev works on a branch and pushes with their own GitHub login (browser/token prompt from
   Git Credential Manager — their credentials, not the owner's):
   ```bash
   git checkout -b my-feature
   # ...edit...
   git add -A && git commit -m "what I changed"
   git push -u origin my-feature      # then open a Pull Request on GitHub
   ```
4. To run the automation, the dev only needs the repo secret set (owner does this once).
   They never need the owner's Discord or GitHub credentials — the Action reads the secret.

Everything a new person needs is in this file + README.md. Point them here first.

---

## 8. Configuration knobs (`config.py`)

- `COINS` — which coins (env `COINS` overrides).
- `HAR_LOOKBACKS_H`, `FWD_H` — vol model windows / forecast horizon.
- `STORM_PCTILE`, `CALM_PCTILE`, `EXPANSION_*` — regime thresholds.
- `FUNDING_EXTREME`, `OI_BUILD_PCT`, `WHALE_USD` — derivatives/flow flags.

---

## 9. Roadmap

- **Phase 1 (now):** pipeline + Discord + forecast log. ✅
- **Phase 2:** score the vol forecasts vs realized (public accuracy scorecard = the trust moat);
  add liquidation-cluster levels; add more exchanges' taker flow for true cross-exchange CVD.
- **Phase 3:** tiers (free 1 coin → $49–99 retail → $499–1k allocator/managed).

---

## 10. Hard rules

- **Never** commit secrets (webhook, tokens). They live in GitHub Actions secrets / local ENV only.
- **Never** ship "buy/sell direction" signals — it's a coin flip, the industry loses money
  (UTS 2025: avg paid signal group −4.2%), and it kills the brand. Our product is *risk*.
- Keep every forecast logged and honest. The track record IS the business.
