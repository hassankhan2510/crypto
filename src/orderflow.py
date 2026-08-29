"""Order-flow CONTEXT (not signals):
 - taker CVD lean from Binance hourly taker volume (4h/24h)
 - cross-exchange aggregated CVD from live trades (Binance+Coinbase+OKX)
 - VPIN flow-toxicity proxy (how one-sided / informed the flow is)
 - whale vs retail split
Framed as 'where the pressure is', never 'buy here'."""
import numpy as np, pandas as pd
from config import WHALE_USD
from src import exchanges as ex

def cvd_state(hourly):
    step = hourly["cvd_step"].astype(float); qv = hourly["qv"].astype(float)
    def lean(n):
        net = step.iloc[-n:].sum(); tot = qv.iloc[-n:].sum()
        return (net / tot * 100) if tot > 0 else 0.0
    l4, l24 = lean(4), lean(24)
    def word(x): return "buyers" if x > 3 else "sellers" if x < -3 else "balanced"
    return {"cvd_4h_pct": l4, "cvd_24h_pct": l24, "cvd_4h": word(l4), "cvd_24h": word(l24)}

def agg_cvd(coin, binance_agg):
    """True cross-exchange aggressor lean from recent trades on 3 venues."""
    books = {"binance": binance_agg, "coinbase": ex.coinbase_trades(coin, 1000),
             "okx": ex.okx_trades(coin, 500)}
    per = {}
    tot_net = tot_vol = 0.0
    for name, df in books.items():
        if df is None or df.empty or "usd" not in df: continue
        net = df.loc[df["buy"], "usd"].sum() - df.loc[~df["buy"], "usd"].sum()
        vol = df["usd"].sum()
        if vol <= 0: continue
        per[name] = net / vol * 100
        tot_net += net; tot_vol += vol
    if tot_vol <= 0:
        return {"agg_pct": 0.0, "per": {}, "venues": 0, "divergence": False}
    agg = tot_net / tot_vol * 100
    # divergence = venues disagree in sign (informative: local vs global demand)
    signs = [np.sign(v) for v in per.values() if abs(v) > 3]
    divergence = len(set(signs)) > 1
    return {"agg_pct": agg, "per": per, "venues": len(per), "divergence": divergence}

def vpin(binance_agg, buckets=20):
    """VPIN flow-toxicity proxy: mean |buy-sell| imbalance across equal-$ buckets.
    ~0 balanced, ->1 highly one-sided/informed flow (adverse-selection / move brewing)."""
    if binance_agg is None or binance_agg.empty: return None
    df = binance_agg.copy()
    df["signed"] = np.where(df["buy"], df["usd"], -df["usd"])
    tot = df["usd"].sum()
    if tot <= 0: return None
    size = tot / buckets
    cum = df["usd"].cumsum()
    df["bucket"] = (cum // size).clip(upper=buckets - 1)
    g = df.groupby("bucket")
    imb = (g["signed"].sum().abs() / g["usd"].sum()).mean()
    return float(imb)

def whale_retail(agg):
    if agg is None or agg.empty:
        return {"whale": "n/a", "retail": "n/a", "whale_net_usd": 0.0, "whale_share_pct": 0.0}
    whale = agg[agg["usd"] >= WHALE_USD]; retail = agg[agg["usd"] < WHALE_USD]
    def net(df): return df.loc[df["buy"], "usd"].sum() - df.loc[~df["buy"], "usd"].sum()
    wn, rn = net(whale), net(retail); tot = agg["usd"].sum() + 1
    def word(x): return "balanced" if abs(x) < tot * 0.02 else ("buying" if x > 0 else "selling")
    return {"whale": word(wn), "retail": word(rn), "whale_net_usd": wn, "retail_net_usd": rn,
            "whale_share_pct": (whale["usd"].sum() / tot * 100) if len(whale) else 0.0}
