"""Track-record scorer -- the trust moat.

Two fixes over the old version:

1. It graded the WRONG HORIZON. `later.iloc[0]` took the EARLIEST row inside a
   +/-3h tolerance window, so a 24h band was consistently graded against a ~21h
   outcome, biasing coverage upward. It now picks the row NEAREST the target time
   and records the actual elapsed hours so the drift is visible.

2. It only scored the 24h band. The intraday horizons (1h/4h) are the ones the
   product now leads with -- and measured OOS they are the more skilful ones --
   so they are scored too.

Coverage is the honest metric: a well-calibrated 1-sigma band contains the
outcome ~68% of the time. Above that we are too wide (useless), below it we are
too narrow (dangerous).
"""
import os
import pandas as pd
from datetime import timedelta

LOG = os.path.join(os.path.dirname(__file__), "..", "data", "forecasts.csv")

# (column prefix, hours ahead, tolerance hours, label)
HORIZON_COLS = [
    ("h1",  1,  0.6, "1h"),
    ("h4",  4,  1.0, "4h"),
    ("h24", 24, 2.0, "24h"),
]


def _nearest(g, target, tol):
    """The row closest to `target`, within `tol` hours. None if nothing is close."""
    lo, hi = target - timedelta(hours=tol), target + timedelta(hours=tol)
    w = g[(g["ts_utc"] >= lo) & (g["ts_utc"] <= hi)]
    if w.empty:
        return None, None
    idx = (w["ts_utc"] - target).abs().idxmin()
    row = w.loc[idx]
    return row, float((row["ts_utc"] - target).total_seconds() / 3600.0)


def score():
    if not os.path.exists(LOG):
        return None
    df = pd.read_csv(LOG, parse_dates=["ts_utc"])
    if len(df) < 10:
        return {"n": 0, "note": "building history -- scorecard needs ~2 days of runs"}

    out = {"per_horizon": {}, "per_coin": {}, "n": 0, "covered": 0}
    for coin, g in df.groupby("coin"):
        g = g.sort_values("ts_utc").reset_index(drop=True)
        coin_n = coin_cov = 0
        for pref, hours, tol, label in HORIZON_COLS:
            lo_c, hi_c = f"{pref}_lo", f"{pref}_hi"
            if lo_c not in g.columns:
                continue
            n = cov = 0
            drift = []
            for _, row in g.iterrows():
                if pd.isna(row.get(lo_c)) or not row.get(lo_c):
                    continue
                later, dh = _nearest(g, row["ts_utc"] + timedelta(hours=hours), tol)
                if later is None:
                    continue
                n += 1; drift.append(abs(dh))
                if row[lo_c] <= later["price"] <= row[hi_c]:
                    cov += 1
            if n >= 3:
                h = out["per_horizon"].setdefault(label, {"n": 0, "cov": 0, "drift": []})
                h["n"] += n; h["cov"] += cov; h["drift"] += drift
                if label == "24h":
                    coin_n += n; coin_cov += cov
        if coin_n >= 3:
            out["per_coin"][coin] = {"n": coin_n, "coverage_pct": round(100 * coin_cov / coin_n, 1)}

    for label, h in out["per_horizon"].items():
        h["coverage_pct"] = round(100 * h["cov"] / h["n"], 1) if h["n"] else None
        h["mean_drift_h"] = round(sum(h["drift"]) / len(h["drift"]), 2) if h["drift"] else None
        h.pop("drift", None)
        out["n"] += h["n"]; out["covered"] += h["cov"]

    out["coverage_pct"] = round(100 * out["covered"] / out["n"], 1) if out["n"] else None
    return out


def summary_text(s):
    if not s:
        return None
    if s.get("n", 0) == 0:
        return s.get("note", "no track record yet")
    parts = [f"{lab} {h['coverage_pct']}% (n={h['n']})"
             for lab, h in sorted(s.get("per_horizon", {}).items())]
    line = f"📋 Track record: {s['n']} scored forecasts · range coverage — " + " · ".join(parts)
    return line + "  |  well-calibrated ≈ 68%"


if __name__ == "__main__":
    import json
    print(json.dumps(score(), indent=2, default=str))
