"""Crypto Vol & Risk Intel — main run.
Pull multi-exchange data -> compute vol/regime + order-flow + derivatives ->
synthesize honest per-coin report -> print, log (track record), post to Discord.

Run:  python main.py            (posts to Discord if DISCORD_WEBHOOK_URL set)
      python main.py --dry      (never posts; console only)
"""
import sys
from config import COINS, BRAND
from src import exchanges as ex
from src import volatility, orderflow, synthesize, discord_post, track

def analyze_coin(coin):
    hourly = ex.binance_klines(coin, "1h", 1000)          # OHLCV + taker flow
    spot24 = ex.binance_24h(coin)
    agg = None
    try: agg = ex.binance_aggtrades(coin, 1000)
    except Exception: pass
    vol = volatility.analyze(hourly)
    of  = orderflow.cvd_state(hourly)
    wr  = orderflow.whale_retail(agg)
    deriv = {"funding": ex.funding_rate(coin),
             "oi_chg": ex.open_interest_change(coin),
             "long_short": ex.long_short_ratio(coin)}
    xprice = {"coinbase": ex.coinbase_price(coin), "okx": ex.okx_price(coin)}
    return synthesize.build_report(coin, spot24, vol, of, wr, deriv, xprice)

def main():
    dry = "--dry" in sys.argv
    print(f"{BRAND} — analyzing {', '.join(COINS)}\n")
    reports = []
    for coin in COINS:
        try:
            rep = analyze_coin(coin)
            reports.append(rep)
            print(synthesize.console(rep))
        except Exception as e:
            print(f"  !! {coin} failed: {e}")
    if not reports:
        print("No reports produced."); return
    print("\n" + "=" * 60)
    track.log(reports)
    if not dry:
        discord_post.post(reports)
    else:
        print("  [dry run] not posting to Discord.")

if __name__ == "__main__":
    main()
