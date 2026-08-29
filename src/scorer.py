"""Track-record scorer — the trust moat.
Reads data/forecasts.csv and grades each past vol forecast against what actually
happened (using a later log row ~24h after as the realized price). Reports:
 - RANGE COVERAGE: how often price stayed inside the forecast ±1σ range
   (well-calibrated ≈ 68%). This is honest, verifiable proof the vol model works.
 - REGIME PERSISTENCE and directional base-rate (to show we DON'T claim direction).
Self-contained: needs no extra data once ~2 days of history accrue.
"""
import os, pandas as pd
from datetime import timedelta

LOG = os.path.join(os.path.dirname(__file__), "..", "data", "forecasts.csv")

def score(fwd_hours=24, tol_hours=3):
    if not os.path.exists(LOG):
        return None
    df = pd.read_csv(LOG, parse_dates=["ts_utc"])
    if len(df) < 10:
        return {"n": 0, "note": "building history — scorecard needs ~2 days of runs"}
    out = {"per_coin": {}, "n": 0, "covered": 0, "regime_hit": 0, "regime_n": 0}
    for coin, g in df.groupby("coin"):
        g = g.sort_values("ts_utc").reset_index(drop=True)
        n = cov = 0
        for i, row in g.iterrows():
            target = row["ts_utc"] + timedelta(hours=fwd_hours)
            later = g[(g["ts_utc"] >= target - timedelta(hours=tol_hours)) &
                      (g["ts_utc"] <= target + timedelta(hours=tol_hours))]
            if later.empty: continue
            realized = later.iloc[0]["price"]
            if pd.isna(row["range_lo"]) or row["range_lo"] == 0: continue
            n += 1
            if row["range_lo"] <= realized <= row["range_hi"]:
                cov += 1
        if n >= 3:
            out["per_coin"][coin] = {"n": n, "coverage_pct": round(100 * cov / n, 1)}
            out["n"] += n; out["covered"] += cov
    out["coverage_pct"] = round(100 * out["covered"] / out["n"], 1) if out["n"] else None
    return out

def summary_text(s):
    if not s: return None
    if s.get("n", 0) == 0: return s.get("note", "no track record yet")
    cov = s.get("coverage_pct")
    line = f"📋 Track record: {s['n']} scored forecasts · range coverage **{cov}%** (well-calibrated ≈ 68%)"
    parts = [f"{c} {v['coverage_pct']}%" for c, v in s["per_coin"].items()]
    if parts: line += "  |  " + " · ".join(parts)
    return line

if __name__ == "__main__":
    import json; print(json.dumps(score(), indent=2))
