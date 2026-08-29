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
