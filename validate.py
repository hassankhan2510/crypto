"""Prove the model, or don't ship the claim.

The README says the volatility forecast is validated out-of-sample. This script
is what makes that statement auditable instead of asserted: it re-runs the exact
production code path (src.volatility) over full history and prints the
walk-forward OOS R2 per coin per horizon, alongside two benchmarks.

Run:  python validate.py
      python validate.py --coins BTC,ETH,SOL --json report.json

Benchmarks
----------
naive     : "next period's vol = last period's vol". The bar any vol model must clear.
constant  : the sample mean. R2 = 0 by construction; a negative R2 means the
            model is worse than saying nothing, which is what the OLD shipped
            config actually did (-0.13 to -0.25 on 42 days of history).
"""
import sys, json
import numpy as np, pandas as pd

from config import (COINS, HORIZONS, HAR_LOOKBACKS_1H, HAR_LOOKBACKS_5M,
                    HISTORY_1H_BARS, HISTORY_5M_BARS, OOS_FRACTION, OOS_REFIT_EVERY)
from src import exchanges as ex
from src.volatility import _design


def _bench_naive(X, y, fwd, frac=OOS_FRACTION):
    """f0 (the shortest trailing RV) used directly as the forecast."""
    n = len(y); start = int(n * frac)
    idx = list(range(start, n, fwd))
    a = np.array([y[i] for i in idx])
    p = np.array([X[i, 1] for i in idx])          # column 1 = shortest lookback RV
    if len(a) < 20:
        return None
    ss = float(((a - a.mean()) ** 2).sum())
    return None if ss <= 0 else float(1 - ((a - p) ** 2).sum() / ss)


def _walkforward(X, y, fwd, frac=OOS_FRACTION, refit=OOS_REFIT_EVERY):
    n = len(y); start = int(n * frac)
    if start < 250 or n - start < 30:
        return None, 0
    P, A, beta = [], [], None
    for k, i in enumerate(range(start, n, fwd)):
        tr = i - fwd
        if tr < 200:
            continue
        if beta is None or k % refit == 0:
            beta, *_ = np.linalg.lstsq(X[:tr], y[:tr], rcond=None)
        P.append(X[i] @ beta); A.append(y[i])
    if len(A) < 20:
        return None, 0
    p, a = np.array(P), np.array(A)
    ss = float(((a - a.mean()) ** 2).sum())
    if ss <= 0:
        return None, len(a)
    return float(1 - ((a - p) ** 2).sum() / ss), len(a)


def validate(coins):
    rows = []
    for coin in coins:
        try:
            h1 = ex.klines(coin, "1h", HISTORY_1H_BARS)
            c5 = ex.klines(coin, "5m", HISTORY_5M_BARS)
        except Exception as e:
            print(f"  !! {coin}: {str(e)[:80]}")
            continue
        print(f"\n{coin}  ({len(h1)} hourly bars = {len(h1)/24:.0f}d, "
              f"{len(c5)} 5m bars = {len(c5)*5/1440:.0f}d)")
        print(f"  {'horizon':<8}{'OOS R2':>10}{'naive':>10}{'n_eval':>9}   verdict")
        for key, interval, n, label in HORIZONS:
            src = c5 if interval == "5m" else h1
            lb = HAR_LOOKBACKS_5M if interval == "5m" else HAR_LOOKBACKS_1H
            X, y, _xl, _s = _design(src["c"].astype(float), lb, n)
            if X is None:
                print(f"  {label:<8}{'insufficient history':>29}")
                continue
            r2, ne = _walkforward(X, y, n)
            nv = _bench_naive(X, y, n)
            ok = (r2 is not None and r2 > 0 and (nv is None or r2 > nv))
            verdict = "PASS" if ok else ("FAIL — worse than naive/constant" if r2 is not None else "n/a")
            print(f"  {label:<8}{('n/a' if r2 is None else f'{r2:+.4f}'):>10}"
                  f"{('n/a' if nv is None else f'{nv:+.4f}'):>10}{ne:>9}   {verdict}")
            rows.append({"coin": coin, "horizon": label, "oos_r2": r2,
                         "naive_r2": nv, "n_eval": ne, "pass": ok,
                         "bars": int(len(src))})
    return rows


def main():
    coins = COINS
    if "--coins" in sys.argv:
        coins = sys.argv[sys.argv.index("--coins") + 1].split(",")

    print("Walk-forward out-of-sample validation")
    print(f"  expanding-window fit, {int(OOS_FRACTION*100)}% train / rest test, "
          f"refit every {OOS_REFIT_EVERY} steps")
    print("  evaluation rows are spaced `fwd` bars apart (non-overlapping) and the")
    print("  training set stops `fwd` bars before each test row, so the rolling")
    print("  forward-sum target cannot leak into the fit.")

    rows = validate(coins)
    if not rows:
        print("\nnothing validated."); return

    df = pd.DataFrame(rows)
    print("\n" + "=" * 62)
    print("SUMMARY — mean OOS R2 by horizon")
    for label, g in df.groupby("horizon", sort=False):
        good = g["oos_r2"].dropna()
        if good.empty:
            continue
        print(f"  {label:<5} mean {good.mean():+.3f}   min {good.min():+.3f}   "
              f"max {good.max():+.3f}   pass {int(g['pass'].sum())}/{len(g)}")
    failed = df[~df["pass"] & df["oos_r2"].notna()]
    if len(failed):
        print("\n  FAILING (do not publish a confidence figure for these):")
        for _, r in failed.iterrows():
            print(f"    {r['coin']} {r['horizon']}  R2 {r['oos_r2']:+.4f}")
    else:
        print("\n  All horizons beat both benchmarks.")

    if "--json" in sys.argv:
        path = sys.argv[sys.argv.index("--json") + 1]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)
        print(f"\n  wrote {path}")


if __name__ == "__main__":
    main()
