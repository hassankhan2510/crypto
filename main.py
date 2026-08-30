"""Crypto Vol & Risk Intel -- main run.

Pipeline: paginated multi-year history -> multi-horizon HAR with walk-forward OOS
R2 -> seasonal forward scaling -> COST GATE -> real-window order flow -> BTC
factor decomposition -> risk map -> track log -> Discord + dashboard.

Run:  python main.py            (posts to Discord if DISCORD_WEBHOOK_URL set)
      python main.py --dry      (console only)
      python main.py --dry --coins BTC,ETH,SOL
"""
import sys
from config import (COINS, BRAND, HISTORY_1H_BARS, HISTORY_5M_BARS,
                    FACTOR_COIN, EXEC_STYLE)
from src import exchanges as ex
from src import (volatility, orderflow, levels as lv, synthesize, discord_post,
                 track, scorer, coinglass, playbook as pb, llm, dashboard, factor,
                 cost)


def _fetch(coin):
    """All the history one coin needs. Cached, so this is cheap after run one."""
    hourly = ex.klines(coin, "1h", HISTORY_1H_BARS)
    try:
        bars5m = ex.klines(coin, "5m", HISTORY_5M_BARS)
    except Exception as e:
        print(f"     [{coin}] 5m history unavailable ({str(e)[:60]}) -- intraday horizons disabled")
        bars5m = None
    return hourly, bars5m


def analyze_coin(coin, hourly, bars5m, fac=None):
    spot24 = ex.binance_24h(coin)
    try:
        agg_tr = ex.binance_aggtrades(coin, 1000)
    except Exception:
        agg_tr = None

    vol = volatility.analyze(hourly, bars5m)
    of = orderflow.cvd_state(bars5m, hourly)
    agg = orderflow.agg_cvd(coin, agg_tr)
    vpin = orderflow.vpin(bars5m)
    wr = orderflow.whale_retail(agg_tr, spot24["price"])
    vp = lv.volume_profile(hourly)
    deriv = {"funding": ex.funding_rate(coin), "oi_chg": ex.open_interest_change(coin),
             "long_short": ex.long_short_ratio(coin), "top_ls": ex.top_trader_ls(coin),
             "taker_ls": ex.taker_ls(coin), "liq": coinglass.liquidations(coin)}
    xprice = {"coinbase": ex.coinbase_price(coin), "okx": ex.okx_price(coin)}
    mvol = ex.multi_volume(coin)

    rep = synthesize.build_report(coin, spot24, vol, of, agg, vp, wr, deriv,
                                  xprice, mvol, vpin, fac)
    rep["playbook"] = pb.build(rep)
    rep["ai_plain"] = llm.easy_language(llm.facts_string(rep))   # None if no OPENROUTER key
    return rep


def main():
    dry = "--dry" in sys.argv
    coins = COINS
    if "--coins" in sys.argv:
        coins = sys.argv[sys.argv.index("--coins") + 1].split(",")

    print(f"{BRAND} — analyzing {', '.join(coins)}")
    print(f"  round-trip cost model: {cost.round_trip_pct():.3f}% "
          f"({cost.round_trip_bps():.1f} bps, {EXEC_STYLE} execution)\n")

    # ---- 1. history for every coin (needed before the factor model) ----
    frames = {}
    for coin in coins:
        try:
            frames[coin] = _fetch(coin)
            h = frames[coin][0]
            print(f"  [{coin}] {len(h)} hourly bars ({len(h)/24:.0f}d)"
                  + (f", {len(frames[coin][1])} 5m bars" if frames[coin][1] is not None else ""))
        except Exception as e:
            print(f"  !! {coin} history failed: {str(e)[:90]}")

    if not frames:
        print("No history available."); return

    # ---- 2. factor decomposition (BTC + residuals) ----
    dec = factor.decompose({c: f[0] for c, f in frames.items()})
    if dec:
        print(f"\n  factor = {FACTOR_COIN} over {dec['_factor']['n_bars']} bars")

    # ---- 3. per-coin analysis ----
    reports = []
    for coin in coins:
        if coin not in frames:
            continue
        try:
            hourly, bars5m = frames[coin]
            rep = analyze_coin(coin, hourly, bars5m, (dec or {}).get(coin))
            reports.append(rep)
            print(synthesize.console(rep))
        except Exception as e:
            import traceback
            print(f"  !! {coin} failed: {type(e).__name__}: {e}")
            if "--debug" in sys.argv:
                traceback.print_exc()

    if not reports:
        print("No reports produced."); return

    portfolio = factor.market_summary(reports, dec)
    print("\n" + "=" * 70)
    if portfolio:
        print(f"MARKET: {portfolio['risk']} — {portfolio['note']}")
        if portfolio.get("tradeable"):
            print(f"  clears costs right now: {', '.join(portfolio['tradeable'])}")
        else:
            print("  clears costs right now: NOTHING")

    track.log(reports)
    sc = scorer.score()
    track_line = scorer.summary_text(sc)
    if track_line:
        print("  " + track_line.replace("**", ""))

    dashboard.write(reports, portfolio, track_line)
    if not dry:
        discord_post.post(reports, portfolio, track_line)
    else:
        print("  [dry run] not posting to Discord.")


if __name__ == "__main__":
    main()
