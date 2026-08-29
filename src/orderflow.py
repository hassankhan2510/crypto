"""Order-flow CONTEXT (not signals): real taker CVD + whale-vs-retail split.
Framed as 'where the pressure/liquidity is', never 'buy here'."""
import numpy as np, pandas as pd
from config import WHALE_USD

def cvd_state(hourly):
    """Aggressive-flow lean over 4h and 24h from Binance taker volume."""
    step = hourly["cvd_step"].astype(float)
    qv = hourly["qv"].astype(float)
    def lean(n):
        net = step.iloc[-n:].sum()
        tot = qv.iloc[-n:].sum()
        return (net / tot * 100) if tot > 0 else 0.0   # net aggressive % of volume
    l4, l24 = lean(4), lean(24)
    def word(x): return "buyers" if x > 3 else "sellers" if x < -3 else "balanced"
    return {"cvd_4h_pct": l4, "cvd_24h_pct": l24, "cvd_4h": word(l4), "cvd_24h": word(l24)}

def whale_retail(agg):
    """Split recent aggressor volume into whale vs retail net lean ($)."""
    if agg is None or agg.empty:
        return {"whale": "n/a", "retail": "n/a", "whale_net_usd": 0.0}
    whale = agg[agg["usd"] >= WHALE_USD]
    retail = agg[agg["usd"] < WHALE_USD]
    def net(df):
        return df.loc[df["buy"], "usd"].sum() - df.loc[~df["buy"], "usd"].sum()
    wn, rn = net(whale), net(retail)
    def word(x, scale):
        if abs(x) < scale: return "balanced"
        return "buying" if x > 0 else "selling"
    tot = agg["usd"].sum() + 1
    return {"whale": word(wn, tot * 0.02), "retail": word(rn, tot * 0.02),
            "whale_net_usd": wn, "retail_net_usd": rn,
            "whale_share_pct": len(whale) and whale["usd"].sum() / tot * 100 or 0.0}
