"""Immutable forecast log — the track-record moat. Each run appends a row;
the file is git-committed so every forecast is timestamped and tamper-evident.
`score()` later grades vol forecasts against what actually happened."""
import os, csv, time

LOG = os.path.join(os.path.dirname(__file__), "..", "data", "forecasts.csv")
COLS = ["ts_utc", "coin", "price", "fc_move_pct", "range_lo", "range_hi",
        "regime", "regime_pctile", "expansion", "confidence",
        "funding", "oi_chg", "long_short", "cvd_24h_pct"]

def log(reports):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    new = not os.path.exists(LOG)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new: w.writerow(COLS)
        for r in reports:
            v = r["vol"] or {}
            w.writerow([ts, r["coin"], f"{r['price']:.4f}",
                        f"{v.get('move_pct',0):.3f}", f"{v.get('range_lo',0):.2f}",
                        f"{v.get('range_hi',0):.2f}", v.get("regime",""),
                        f"{v.get('regime_pctile',0):.1f}", v.get("expansion",""),
                        v.get("confidence",""),
                        r.get("funding",""), r.get("oi_chg",""), r.get("long_short",""),
                        f"{(r['of'] or {}).get('cvd_24h_pct',0):.2f}"])
    print(f"  [track] logged {len(reports)} forecasts -> data/forecasts.csv")
