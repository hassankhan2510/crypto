# BUILDLOG.md — full context & decisions behind Crypto Vol & Risk Intel

> Narrative log of what was built, why, and what we learned. Pair with `CONTEXT.md`
> (how to run/extend) and `README.md` (public overview). This file = the "why".

---

## 0. Origin — why this product exists

This is a **pivot from a year of gold/forex research** (in `D:\tradingclaude`). That research
proved, ~25 experiments deep + two written papers, one thing conclusively:

> **Volatility (move size) is forecastable. Direction (up/down) is NOT — not by any chart
> setup, indicator, ML model, cross-asset graph, or order-flow proxy available to retail,
> net of cost.**

Key proofs carried into this product:
- **Paper 2 (Realized Volatility):** HAR vol model, OOS R² 0.11–0.43 across BTC/ETH/PAXG/XAU;
  matched directional control = −4 to −8 bp/trade (no edge). Volatility is the real signal.
- **Paper 1 (Tokenized Gold):** PAXG↔spot gold cointegrated; spot LEADS PAXG (PAXG can't
  predict gold). Order-flow proxies follow, don't lead.
- Direction signal services lose money (UTS 2025 study: avg paid group −4.2%, only 11% beat holding BTC).

So this product **sells validated RISK intelligence, never buy/sell signals.** That honesty
IS the moat.

---

## 1. Competitive research (done 2026-08-29 via web search)

| Player | What it does | Price |
|---|---|---|
| **Buildix** | CVD, bucketed CVD (whale/retail), VPIN, OBI, OFI, Kyle λ, volume profile, whale tracking, AI advisor, 530+ pairs, 5 exchanges | **$9/mo** |
| **Coinglass** | Aggregates liquidations/OI/funding/orderbook from 30+ exchanges; liquidation heatmaps | free / **$40/mo** |
| **FundingPulse** | Free API: funding, OI, long/short, liquidations, cross-exchange spreads (6 exchanges, 60s) | free |
| Retail signal groups | direction signals | ~$20–290/mo (and mostly lose) |

**Implications that shaped strategy:**
- "Merge order flow → Discord" is a **solved, cheap, crowded** market. Cannot win on that alone,
  and **$1k/mo retail is a mirage** (retail caps ~$200; those services lose money).
- Premium ($500–1k) is real only for **allocators/funds** with **verifiable track records** and
  a managed/decision layer — not retail scalp signals.

---

## 2. Positioning decisions

1. **Product = "Validated Crypto Volatility & Risk Intelligence."** Not signals.
2. **Dual-audience output** (the user's explicit ask): every coin report has
   🟢 *plain words* (a normal person + heavy passive investor understands) AND
   📊 *pro block* (CVD/VPIN/levels/funding for a 10-yr trader).
3. **Moats vs Buildix/Coinglass:** (a) validated *forward* vol forecast (they're descriptive),
   (b) honest "when NOT to trade" + risk verdicts, (c) **git-committed immutable track record**,
   (d) a **portfolio/market overview** aimed at non-trading allocators.
4. **Target premium segment:** wealthy allocators who don't trade — risk-regime guidance, not scalps.

---

## 3. Architecture

```
GitHub Actions cron (*/30 * * * *)
  → pull free multi-exchange data
  → compute vol/regime + cross-exchange order flow + VPIN + derivatives + levels
  → synthesize dual-audience report + market overview + track-record line
  → POST Discord embeds  +  commit data/forecasts.csv (track record)
```
Files: `main.py`, `config.py`, `src/{http,exchanges,volatility,orderflow,levels,synthesize,discord_post,track,scorer}.py`, `.github/workflows/run.yml`.

---

## 4. Phases built (all done 2026-08-29)

- **Phase 1:** multi-exchange pull → HAR vol forecast + regime → order-flow + derivatives →
  honest verdict → Discord + forecast log. Tested live (BTC/ETH/SOL).
- **Phase 2:** `scorer.py` (range-coverage vs realized = track record); `levels.py`
  (volume-profile POC/S-R + estimated liquidation clusters); `orderflow.py` upgraded with
  **cross-exchange aggregated CVD** (Binance+Coinbase+OKX) + divergence flag + **VPIN**.
- **Phase 3:** dual-audience reports (plain + pro), **portfolio/market overview**, **TIER** env
  (free/retail/pro).
- **Phase 4 (done):** richer derivatives. Added FREE keyless Binance-futures signals —
  **top-trader long/short position ratio** (smart-money lean) and **taker buy/sell ratio**
  (aggressive futures flow). Added **optional Coinglass** (`src/coinglass.py`, gated on
  `COINGLASS_API_KEY` free tier) for **real aggregated 24h liquidations**; degrades to
  estimated liq levels without a key. Liquidation context also surfaced in plain words
  ("$X of longs got force-sold in 24h").

- **Phase 5 (done 2026-08-29):** **Scenario Playbook** (`src/playbook.py`) — if-then risk map
  per coin (key zones + liq clusters → up/down scenarios with invalidation + R:R; honest, both
  sides, no "buy now"). **AI easy-language** (`src/llm.py`) via OpenRouter free model
  (`OPENROUTER_API_KEY`), constrained to EXPLAIN only (no direction/buy/sell/invented numbers);
  falls back to template plain-words without a key. **Free web dashboard** (`src/dashboard.py`
  → `docs/`, GitHub Pages) — cards with plain words + metrics + playbook, auto-refresh 60s,
  **live price via client-side Binance WebSocket**. Verified rendering in-browser.

### Data-source verdicts (tested 2026-08-29)
- Coinglass: **all endpoints need an API key** (401 without); free tier delayed → dropped, opt-in only.
- FundingPulse (Apify): needs an Apify token → skipped (not truly keyless).
- **Recommended free alt = Hyperliquid public API** (no key, no rate limits; funding/OI + full
  on-chain whale positions + liquidations). NEXT to integrate.
- **Binance futures free/keyless winners added:** `topLongShortPositionRatio`, `takerlongshortRatio`.

### Real-time answer (for the dashboard)
Static Pages can't server-push. Solution shipped: **live price ticks client-side (browser→Binance
WS)**, analysis refreshes every 30 min (cron). Fully live analytics = Phase-5 VPS.

---

## 5. Data-source reachability findings (from sandbox; prod = GitHub US runners)

| Source | Status | Notes |
|---|---|---|
| Binance spot (`api.binance.com`) | ✅ fast (~0.9s) | primary: OHLCV + real taker CVD, aggTrades, 24h |
| Binance futures (`fapi.binance.com`) | ✅ but slow (~7s/call) here | funding, OI hist, long/short. tries=2 |
| Coinbase (`api.exchange.coinbase.com`) | ✅ fast (~0.5s) | price, trades (taker side), stats |
| OKX (`www.okx.com`) | ❌ geo-blocked here | fails instantly; fail-fast (tries=1). Likely OK on GitHub US |

All **secondary** calls fail-fast so a slow/blocked venue can't stall a run. Core = Binance + Coinbase.

---

## 6. Gotchas

- **OpenBLAS memory error** on this Windows/Python: run with `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`
  (set in the workflow too).
- **CRLF warnings** on commit are harmless (Windows line endings).
- **fapi slowness** local; fine in prod.
- Python: `D:\SOFTEWHERES\python\python.exe`; `PYTHONUTF8=1` for console.

---

## 7. Repo / deploy state

- Repo: **https://github.com/hassankhan2510/crypto** (branch `main`). Commits: `71d1171` (Phase 1),
  `9827971` (Phases 2–3).
- **Owner's remaining steps:** create Discord webhook → repo secret `DISCORD_WEBHOOK_URL` →
  make repo **Public** (unlimited Actions minutes) → Actions → Run workflow.
- New devs: use their own GitHub login; onboarding in `CONTEXT.md §7`. Never share owner creds.

---

## 8. Hard rules (do not break)

- Never commit secrets (webhook/API keys) — GitHub Actions secrets / local ENV only.
- Never ship buy/sell direction signals — proven a coin, industry loses money, kills the brand.
- Keep every forecast logged & honest. The track record IS the business.

---

## 6. Audit & rebuild — 2026-08-30

An adversarial review measured the shipped code against live data instead of reading it.
Everything below is a number, not an opinion. All fixes are in.

### 6.1 The central claim was false

`volatility._har` computed R² on the same rows it fitted and the README called it
"validated out-of-sample". On the shipped config (1000 hourly bars = 42 days):

| coin | reported (in-sample) | **true walk-forward OOS** |
|---|---|---|
| BTC | 0.288 | **−0.131** |
| ETH | 0.183 | **−0.254** |
| SOL | 0.406 → "HIGH confidence" | **−0.203** |

Negative R² = worse than predicting the mean.

**Root cause was the data window, not the model.** Binance caps klines at 1000 rows;
the old code took the cap as the dataset. `HAR_HISTORY_H` existed in config and was
never imported. With paginated 2-year history the same model gives **+0.21 to +0.26**,
matching Paper 2. `exchanges.klines()` now paginates and caches to disk.

### 6.2 The intraday horizons were the good ones all along

`multi_short` (30m/1h from 5m bars) was added last, scored never, and used nowhere.
Measured walk-forward, non-overlapping, with a `fwd`-bar leakage gap:

| horizon | mean OOS R² | vs naive |
|---|---|---|
| 30m | +0.396 | 3/3 beat |
| 1h  | **+0.435** | 3/3 beat |
| 4h  | **+0.449** | 3/3 beat |
| 24h | +0.318 | 3/3 beat |

The 24h horizon everything was built around is the **weakest**. 1h is now the headline
and every horizon is logged and scored. `validate.py` reproduces this table on demand
and runs daily in CI.

### 6.3 Seasonality: the obvious implementation is worse than nothing

Crypto has a real hour-of-day profile (BTC 2.18×, ETH 1.96×, SOL 1.84× in mean |return|;
peak 14:00 UTC, trough ~10:00 UTC). The intuitive fix — forecast, then multiply by the
seasonal factor of the window ahead — **reduces** OOS R², because the HAR's short
lookback already encodes the current hour, so the multiplier double-counts:

| | none | multiplicative | **fitted feature** |
|---|---|---|---|
| BTC 30m | +0.395 | +0.373 | **+0.422** |
| BTC 4h  | +0.444 | +0.449 | **+0.497** |
| SOL 1h  | +0.411 | +0.386 | **+0.429** |

`log(forward seasonal scale)` is now a column in the design matrix. Wins 9/9.

### 6.4 Order flow was 143 seconds of data wearing a suit

Measured on BTC: Binance `aggTrades limit=1000` spans **142.98 seconds** ($509k notional);
Coinbase 1000 trades spans **531.2 seconds**. The old `agg_cvd()` **summed** them into one
"cross-exchange aggregated CVD", and the venue "divergence" flag compared two different
time periods. VPIN ran on 20 buckets × 50 trades.

Now: CVD comes from 5m klines' taker-buy quote volume (69 days, no extra API calls), every
metric carries its **30-day percentile**, VPIN uses equal-dollar-volume buckets over weeks,
and the cross-venue read trims all venues to a **common window** and prints its length.

### 6.5 Fabricated levels, and a direction signal in a product that forbids them

`liquidation_levels()` was `price × (1 − 1/L)` for L in (25,50,100) — i.e. −4%/−2%/−1%
from spot, always, forever, with no position data. `playbook.build()` used it as the
**invalidation (stop) level**, and emitted `long-watch`/`short-watch` with targets and
R:R — the exact thing §10 of CONTEXT.md forbids, computed from two invented inputs.

Both deleted. Levels are volume-profile only (POC + 70% value area, honestly labelled).
The playbook is now a cost table + timing + crowding risks, with no side and no target.

### 6.6 Everything else

- **Cost gate added** (`src/cost.py`) — the product had no notion of what a trade costs.
  BTC 30m: fees are 68% of the mean move. Now the headline horizon is the shortest one
  that clears the toll, and `DEAD` overrides any regime label.
- **Regime anchored** — a percentile alone called the top of a dead month a STORM. It now
  also has to clear 8× round-trip cost. Measured: the old label flipped within its own
  24h forecast horizon **54%** of the time.
- **Six coins → one factor.** Hourly corr BTC–ETH 0.82, BTC–SOL 0.77; BTC explains 67%/60%
  of their variance. `factor.py` reports beta + idiosyncratic residual and flags a coin only
  when its residual vol is in its own top 30%.
- **Scorer fixed** — `later.iloc[0]` took the *earliest* row in a ±3h window, grading a ~21h
  outcome against a 24h band. Now picks the nearest row, records drift, scores all horizons.
- **The track record was empty.** `data/forecasts.csv` had a header and zero rows; no CI run
  had ever committed. New schema logs every horizon, its OOS R², and its cost ratio.

## 7. Companion fix — `tradingview/gold_volrange.pine` v2

Audited against 20,000 real XAUUSD M15 bars.

- **The seasonality baseline was inverted.** `ta.sma(barRangePct, 500)` is ~5 days and is
  itself hour-contaminated, so the "busy hour" ratio measured this hour vs the last 5 days.
  Busy-hour gate lift on forward |1h move|: **0.70× with the SMA baseline, 1.25× with an
  expanding one.** Whole light: **v1 1.06× → v2 1.40×** (1.42×/1.36× across halves).
- `liveMove` fired on **98.56%** of bars — a constant. The 4-gate and 3-gate lights produced
  identical output. Removed.
- **Horizon mismatch:** gates carry 1.40× lift at 1h and 1.13× at 4h; v1 projected 4h.
- **Pine `var` array bug:** array contents are not rolled back between realtime ticks, so the
  hour profile inflated whichever hour was on screen. Guarded with `barstate.isconfirmed`.
- Added a spread/cost gate (honestly documented as *non-binding on gold* — it passes 98.6%
  there and exists for shorter horizons and wider-spread hours), a scheduled-data flag
  (13:30 UTC = 1.81× the average bar), and live band calibration (terminal 69.5% inside ±1σ
  vs 68% target, but price *touches* the band 58% of the time — the cone is not containment).
