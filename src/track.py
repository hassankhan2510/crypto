"""Immutable forecast log -- the track-record moat. Each run appends a row;
the file is git-committed so every forecast is timestamped and tamper-evident.
`scorer.score()` later grades those bands against what actually happened.

The schema now logs EVERY horizon (1h/4h/24h), the OOS R2 that produced it, and
the cost ratio, so the record can be audited on the intraday horizons the product
actually leads with -- not just the 24h one.

Schema changes are additive and header-aware: if the existing file has an older
header, rows are written against that header and missing columns are left blank,
so an in-flight track record is never corrupted or silently re-based.
"""
import os, csv, time

LOG = os.path.join(os.path.dirname(__file__), "..", "data", "forecasts.csv")

COLS = ["ts_utc", "coin", "price",
        "headline_horizon", "fc_move_pct", "cost_ratio", "cost_state",
        "h1_pct", "h1_lo", "h1_hi", "h1_r2",
        "h4_pct", "h4_lo", "h4_hi", "h4_r2",
        "h24_pct", "h24_lo", "h24_hi", "h24_r2",
        "regime", "regime_pctile", "regime_anchored", "expansion", "confidence",
        "season_now", "funding", "oi_chg", "long_short", "cvd_1h_pct", "beta_to_factor"]


def _fmt(x, spec=None):
    if x is None:
        return ""
    if spec:
        try:
            return format(float(x), spec)
        except (TypeError, ValueError):
            return ""
    return x


def _row(r):
    v = r.get("vol") or {}
    of = r.get("of") or {}
    fac = r.get("factor") or {}
    gate = v.get("headline_gate") or {}
    d = {
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "coin": r["coin"], "price": _fmt(r["price"], ".6f"),
        "headline_horizon": v.get("headline_label", ""),
        "fc_move_pct": _fmt(v.get("move_pct"), ".4f"),
        "cost_ratio": _fmt(gate.get("ratio"), ".2f"),
        "cost_state": gate.get("state", ""),
        "regime": v.get("regime", ""),
        "regime_pctile": _fmt(v.get("regime_pctile"), ".1f"),
        "regime_anchored": int(bool(v.get("regime_anchored"))) if v else "",
        "expansion": v.get("expansion", ""),
        "confidence": v.get("confidence", ""),
        "season_now": _fmt(v.get("season_now"), ".3f"),
        "funding": _fmt(r.get("funding"), ".6f"),
        "oi_chg": _fmt(r.get("oi_chg"), ".2f"),
        "long_short": _fmt(r.get("long_short"), ".3f"),
        "cvd_1h_pct": _fmt(of.get("cvd_1h_pct"), ".2f"),
        "beta_to_factor": _fmt(fac.get("beta"), ".3f"),
    }
    for k in ("h1", "h4", "h24"):
        d[f"{k}_pct"] = _fmt(v.get(f"{k}_pct"), ".4f")
        d[f"{k}_lo"] = _fmt(v.get(f"{k}_lo"), ".6f")
        d[f"{k}_hi"] = _fmt(v.get(f"{k}_hi"), ".6f")
        d[f"{k}_r2"] = _fmt(v.get(f"{k}_r2"), ".4f")
    return d


def log(reports):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    header = COLS
    exists = os.path.exists(LOG) and os.path.getsize(LOG) > 0
    if exists:                                  # respect whatever header is already there
        with open(LOG, "r", encoding="utf-8", newline="") as f:
            first = f.readline().strip()
        if first:
            header = first.split(",")

    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        if not exists:
            w.writeheader()
        for r in reports:
            w.writerow(_row(r))
    print(f"  [track] logged {len(reports)} forecasts -> data/forecasts.csv")
