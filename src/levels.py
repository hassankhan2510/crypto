"""Key price levels a trader actually watches:
 - Volume Profile POC + value-area (high-volume nodes = magnets/support-resistance)
 - Estimated liquidation clusters (perp leverage brackets = where cascades fire)
These are 'where the action tends to happen', honest-labeled as estimates."""
import numpy as np
from config import VP_BINS, VP_WINDOW_H, LEVERAGE_TIERS

def volume_profile(hourly):
    """POC (highest-volume price) + nearest high-volume nodes above/below price."""
    h = hourly.iloc[-VP_WINDOW_H:]
    if len(h) < 20: return None
    price = float(h["c"].iloc[-1])
    lo, hi = float(h["l"].min()), float(h["h"].max())
    if hi <= lo: return None
    edges = np.linspace(lo, hi, VP_BINS + 1)
    mid = (edges[:-1] + edges[1:]) / 2
    vol = np.zeros(VP_BINS)
    for _, r in h.iterrows():                       # spread each bar's volume across its range
        b0 = np.searchsorted(edges, r["l"]) - 1
        b1 = np.searchsorted(edges, r["h"]) - 1
        b0 = max(0, b0); b1 = min(VP_BINS - 1, b1)
        if b1 >= b0:
            vol[b0:b1 + 1] += r["v"] / (b1 - b0 + 1)
    poc = round(float(mid[vol.argmax()]), 2)
    # nearest high-volume nodes (top 30% bins) above / below price
    thresh = np.quantile(vol, 0.70)
    hvn = mid[vol >= thresh]
    above = hvn[hvn > price]; below = hvn[hvn < price]
    res = round(float(above.min()), 2) if len(above) else None
    sup = round(float(below.max()), 2) if len(below) else None
    return {"poc": poc, "support": sup, "resistance": res}

def liquidation_levels(price):
    """Estimated long/short liquidation magnets from common perp leverage.
    Long liq below price, short liq above. These clusters attract price (stop cascades)."""
    longs = sorted({round(price * (1 - 1 / L), 2) for L in LEVERAGE_TIERS}, reverse=True)
    shorts = sorted({round(price * (1 + 1 / L), 2) for L in LEVERAGE_TIERS})
    return {"long_liq": longs, "short_liq": shorts}   # nearest first
