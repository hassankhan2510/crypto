"""Crypto Vol & Risk Intel — main run (all phases).
Multi-exchange pull -> vol/regime forecast + cross-exchange order flow + VPIN +
derivatives + key levels -> plain-English + pro report -> portfolio overview ->
track-record scorecard -> Discord + forecast log.

Run:  python main.py            (posts to Discord if DISCORD_WEBHOOK_URL set)
      python main.py --dry      (console only)
"""
import sys
from config import COINS, BRAND
from src import exchanges as ex
from src import (volatility, orderflow, levels as lv, synthesize, discord_post,
                 track, scorer, coinglass, playbook as pb, llm, dashboard)

def analyze_coin(coin):
    hourly = ex.binance_klines(coin, "1h", 1000)
    spot24 = ex.binance_24h(coin)
    try: agg_tr = ex.binance_aggtrades(coin, 1000)
    except Exception: agg_tr = None
    vol   = volatility.analyze(hourly)
    of    = orderflow.cvd_state(hourly)
    agg   = orderflow.agg_cvd(coin, agg_tr)
    vpin  = orderflow.vpin(agg_tr)
    wr    = orderflow.whale_retail(agg_tr)
    vp    = lv.volume_profile(hourly)
    lvls  = lv.liquidation_levels(spot24["price"])
    deriv = {"funding": ex.funding_rate(coin), "oi_chg": ex.open_interest_change(coin),
             "long_short": ex.long_short_ratio(coin), "top_ls": ex.top_trader_ls(coin),
             "taker_ls": ex.taker_ls(coin), "liq": coinglass.liquidations(coin)}
    xprice = {"coinbase": ex.coinbase_price(coin), "okx": ex.okx_price(coin)}
    mvol = ex.multi_volume(coin)
    rep = synthesize.build_report(coin, spot24, vol, of, agg, vp, wr, deriv, xprice, mvol, lvls, vpin)
    rep["playbook"] = pb.build(rep)
    rep["ai_plain"] = llm.easy_language(llm.facts_string(rep))   # None if no OPENROUTER key
    return rep

def main():
    dry = "--dry" in sys.argv
    print(f"{BRAND} — analyzing {', '.join(COINS)}\n")
    reports = []
    for coin in COINS:
        try:
            rep = analyze_coin(coin); reports.append(rep)
            print(synthesize.console(rep))
        except Exception as e:
            print(f"  !! {coin} failed: {e}")
    if not reports:
        print("No reports produced."); return

    portfolio = synthesize.portfolio_summary(reports)
    print("\n" + "=" * 60)
    if portfolio:
        print(f"MARKET: {portfolio['risk']} — {portfolio['note']}")

    track.log(reports)
    sc = scorer.score(); track_line = scorer.summary_text(sc)
    if track_line: print("  " + track_line.replace("**", ""))

    dashboard.write(reports, portfolio, track_line)     # GitHub Pages
    if not dry:
        discord_post.post(reports, portfolio, track_line)
    else:
        print("  [dry run] not posting to Discord.")

if __name__ == "__main__":
    main()
