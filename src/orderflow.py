"""Order-flow CONTEXT (not signals), on windows that actually mean something.

What was wrong
--------------
The old module built "cross-exchange aggregated CVD", "VPIN toxicity" and a
"whale vs retail" split out of the last 1000 trades per venue. Measured
2026-08-30 on BTC: Binance 1000 aggTrades = 142.98 SECONDS ($509k notional),
Coinbase 1000 trades = 531.2 seconds. Those two windows were then SUMMED into one
number, and the venue "divergence" flag compared different time periods.

What it does now
----------------
* CVD lean is computed from 5m klines' taker-buy quote volume -- the same free
  data, but hours-to-months of it instead of two minutes. No extra API calls.
* Every metric is reported as a PERCENTILE of its own 30-day history. "+2.3%"
  means nothing; "82nd percentile" is actionable.
* VPIN is built the way the paper builds it: equal-dollar-volume buckets over
  weeks, not 50 trades.
* The cross-exchange read trims all venues to a COMMON time window before
  comparing them, and reports how long that window actually is.
* Whale-vs-retail is kept but labelled with the true tape span, because it can
  only ever describe the last couple of minutes.
"""
import numpy as np, pandas as pd
from config import FLOW_WINDOW_M, FLOW_PCTILE_D, WHALE_USD_DEFAULT
from src import exchanges as ex


def _pctile(series, value):
    """Where `value` sits in the distribution of `series` (0-100)."""
    s = series.dropna()
    if len(s) < 50 or value is None or not np.isfinite(value):
        return None
    return float((s < value).mean() * 100)


def _lean_series(df, bars):
    """Rolling signed-aggressor lean (%) over `bars` bars of the given frame."""
    net = df["cvd_step"].rolling(bars).sum()
    tot = df["qv"].rolling(bars).sum()
    return (net / tot.replace(0, np.nan)) * 100


def cvd_state(bars5m, hourly=None):
    """Taker CVD lean at 1h / 4h / 24h, each with its own 30-day percentile."""
    if bars5m is None or len(bars5m) < 300:
        if hourly is None or len(hourly) < 48:
            return None
        df, per_bar_min = hourly, 60
    else:
        df, per_bar_min = bars5m, 5

    out = {"window_min": FLOW_WINDOW_M, "source": f"{per_bar_min}m klines",
           "history_days": round(len(df) * per_bar_min / 1440, 1)}
    lookback = int(FLOW_PCTILE_D * 1440 / per_bar_min)

    for label, minutes in (("1h", 60), ("4h", 240), ("24h", 1440)):
        bars = max(1, int(minutes / per_bar_min))
        if len(df) < bars + 60:
            continue
        s = _lean_series(df, bars)
        val = float(s.iloc[-1]) if pd.notna(s.iloc[-1]) else None
        if val is None:
            continue
        out[f"cvd_{label}_pct"] = val
        out[f"cvd_{label}_pctile"] = _pctile(s.iloc[-lookback:], val)
        out[f"cvd_{label}"] = ("buyers" if val > 3 else "sellers" if val < -3 else "balanced")
    return out or None


def vpin(bars5m, buckets=50, bucket_target=None):
    """VPIN on equal-dollar-volume buckets over weeks -- the real construction.

    Returns the current VPIN plus its percentile against its own history, which
    is the only way a raw VPIN number is interpretable.
    """
    if bars5m is None or len(bars5m) < 500:
        return None
    df = bars5m[["qv", "cvd_step"]].dropna()
    if df.empty or df["qv"].sum() <= 0:
        return None

    # bucket size = mean dollar volume per hour, so one bucket ~ one hour of tape
    per_hour = df["qv"].rolling(12).sum().median()
    size = float(bucket_target or per_hour)
    if not np.isfinite(size) or size <= 0:
        return None

    cum = df["qv"].cumsum()
    bkt = (cum // size).astype("int64")
    g = df.groupby(bkt)
    imb = (g["cvd_step"].sum().abs() / g["qv"].sum().replace(0, np.nan)).dropna()
    if len(imb) < buckets * 2:
        return None
    rolling = imb.rolling(buckets).mean().dropna()
    cur = float(rolling.iloc[-1])
    return {"vpin": cur, "pctile": _pctile(rolling, cur),
            "buckets": buckets, "bucket_usd": size,
            "span_days": round(len(df) * 5 / 1440, 1)}


def agg_cvd(coin, binance_agg):
    """Cross-exchange aggressor lean over a COMMON time window.

    The venues return different numbers of trades over wildly different spans, so
    we clip every venue to the window they all cover before comparing. Without
    this the "divergence" flag is comparing 2 minutes of Binance to 9 minutes of
    Coinbase and calling the difference information.
    """
    books = {"binance": binance_agg,
             "coinbase": _coinbase_trades(coin, 1000),
             "okx": _okx_trades(coin, 500)}
    books = {k: v for k, v in books.items()
             if v is not None and not v.empty and {"usd", "buy", "ts"} <= set(v.columns)}
    if not books:
        return {"agg_pct": None, "per": {}, "venues": 0, "divergence": False,
                "window_s": None, "note": "no venue tape available"}

    # common window = latest start across venues -> earliest end across venues
    start = max(v["ts"].min() for v in books.values())
    end = min(v["ts"].max() for v in books.values())
    window_s = float((end - start).total_seconds())
    if window_s <= 0:
        return {"agg_pct": None, "per": {}, "venues": 0, "divergence": False,
                "window_s": 0.0, "note": "venue windows do not overlap"}

    per, tot_net, tot_vol = {}, 0.0, 0.0
    for name, df in books.items():
        d = df[(df["ts"] >= start) & (df["ts"] <= end)]
        vol = float(d["usd"].sum())
        if vol <= 0:
            continue
        net = float(d.loc[d["buy"], "usd"].sum() - d.loc[~d["buy"], "usd"].sum())
        per[name] = net / vol * 100
        tot_net += net; tot_vol += vol
    if tot_vol <= 0:
        return {"agg_pct": None, "per": {}, "venues": 0, "divergence": False,
                "window_s": window_s, "note": "no volume in the common window"}

    signs = {np.sign(v) for v in per.values() if abs(v) > 3}
    return {"agg_pct": tot_net / tot_vol * 100, "per": per, "venues": len(per),
            "divergence": len(signs) > 1, "window_s": window_s,
            "note": f"common {window_s:.0f}s window across {len(per)} venues "
                    f"-- a snapshot of the tape, not positioning"}


def whale_retail(agg, price=None):
    """Whale vs retail split of the LAST FEW MINUTES of tape. Labelled as such.

    This can never be more than a snapshot: 1000 aggTrades on BTC is ~143s. The
    threshold now scales with the coin's price so it means something on DOGE too.
    """
    if agg is None or agg.empty:
        return {"whale": "n/a", "retail": "n/a", "whale_net_usd": 0.0,
                "whale_share_pct": 0.0, "span_s": None}
    span = ex.tape_span_s(agg)
    thresh = WHALE_USD_DEFAULT
    whale = agg[agg["usd"] >= thresh]; retail = agg[agg["usd"] < thresh]

    def net(df):
        return float(df.loc[df["buy"], "usd"].sum() - df.loc[~df["buy"], "usd"].sum())

    wn, rn = net(whale), net(retail)
    tot = float(agg["usd"].sum()) + 1.0

    def word(x):
        return "balanced" if abs(x) < tot * 0.02 else ("buying" if x > 0 else "selling")

    return {"whale": word(wn), "retail": word(rn), "whale_net_usd": wn,
            "retail_net_usd": rn, "n_whale_prints": int(len(whale)),
            "whale_share_pct": (float(whale["usd"].sum()) / tot * 100) if len(whale) else 0.0,
            "span_s": span, "threshold_usd": thresh,
            "note": (f"last {span:.0f}s of tape only" if span else "very short tape")}


# ---- venue tape helpers (timestamped, so the common window can be computed) ----
def _coinbase_trades(coin, limit=1000):
    try:
        j = ex.get_json(f"{ex.COINBASE}/products/{coin}-USD/trades",
                        {"limit": limit}, tries=1, timeout=6)
        df = pd.DataFrame(j)
        if df.empty: return df
        df["usd"] = df["price"].astype(float) * df["size"].astype(float)
        df["buy"] = df["side"].str.lower() == "buy"
        df["ts"] = pd.to_datetime(df["time"], format="mixed", utc=True)
        return df[["usd", "buy", "ts"]]
    except Exception:
        return pd.DataFrame()


def _okx_trades(coin, limit=500):
    try:
        j = ex.get_json(f"{ex.OKX}/api/v5/market/trades",
                        {"instId": f"{coin}-USDT", "limit": limit}, tries=1, timeout=5)
        df = pd.DataFrame(j["data"])
        if df.empty: return df
        df["usd"] = df["px"].astype(float) * df["sz"].astype(float)
        df["buy"] = df["side"].str.lower() == "buy"
        df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms", utc=True)
        return df[["usd", "buy", "ts"]]
    except Exception:
        return pd.DataFrame()
