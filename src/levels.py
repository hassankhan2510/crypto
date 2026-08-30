"""Key price levels a trader actually watches -- only the ones we can honestly compute.

REMOVED: the old `liquidation_levels()`. It was `price * (1 - 1/L)` for
L in (25, 50, 100), i.e. it returned -4% / -2% / -1% from spot, always, forever.
No position data, no maintenance margin, no entry distribution, no open interest
at price -- arithmetic on round numbers, labelled "where cascades fire", and then
used by the playbook AS A STOP LEVEL. Fabricated levels are worse than no levels,
so they are gone. If COINGLASS_API_KEY is set we show REAL aggregated
liquidations instead (src/coinglass.py); otherwise we show nothing.

KEPT: volume profile, with the value area, and honest labelling. A high-volume
node is "price spent a lot of time here", not "price will bounce here".
"""
import numpy as np
from config import VP_BINS, VP_WINDOW_H


def _r(x):
    """Round to a sensible number of decimals for the price's magnitude.
    A flat round(...,2) turns DOGE's $0.083 POC into 0.08 and XRP's into noise."""
    if x is None:
        return None
    ax = abs(x)
    d = 2 if ax >= 100 else 4 if ax >= 1 else 6 if ax >= 0.01 else 8
    return round(float(x), d)


def volume_profile(hourly):
    """POC, 70% value area, and the nearest high-volume nodes above/below price."""
    h = hourly.iloc[-VP_WINDOW_H:]
    if len(h) < 20:
        return None
    price = float(h["c"].iloc[-1])
    lo, hi = float(h["l"].min()), float(h["h"].max())
    if hi <= lo:
        return None

    edges = np.linspace(lo, hi, VP_BINS + 1)
    mid = (edges[:-1] + edges[1:]) / 2
    vol = np.zeros(VP_BINS)
    lows = h["l"].to_numpy(dtype=float)
    highs = h["h"].to_numpy(dtype=float)
    vols = h["v"].to_numpy(dtype=float)
    for lo_i, hi_i, v_i in zip(lows, highs, vols):
        b0 = int(np.clip(np.searchsorted(edges, lo_i, side="right") - 1, 0, VP_BINS - 1))
        b1 = int(np.clip(np.searchsorted(edges, hi_i, side="right") - 1, 0, VP_BINS - 1))
        if b1 < b0:
            b0, b1 = b1, b0
        vol[b0:b1 + 1] += v_i / (b1 - b0 + 1)

    if vol.sum() <= 0:
        return None
    poc_i = int(vol.argmax())
    poc = float(mid[poc_i])

    # 70% value area, grown outward from the POC (standard construction)
    target = vol.sum() * 0.70
    lo_i = hi_i = poc_i
    acc = vol[poc_i]
    while acc < target and (lo_i > 0 or hi_i < VP_BINS - 1):
        take_lo = vol[lo_i - 1] if lo_i > 0 else -1
        take_hi = vol[hi_i + 1] if hi_i < VP_BINS - 1 else -1
        if take_hi >= take_lo:
            hi_i += 1; acc += take_hi
        else:
            lo_i -= 1; acc += take_lo

    thresh = np.quantile(vol, 0.70)
    hvn = mid[vol >= thresh]
    above = hvn[hvn > price]; below = hvn[hvn < price]
    return {
        "poc": _r(poc),
        "val": _r(float(mid[lo_i])),                # value-area low
        "vah": _r(float(mid[hi_i])),                # value-area high
        "hvn_above": _r(float(above.min())) if len(above) else None,
        "hvn_below": _r(float(below.max())) if len(below) else None,
        "window_h": int(min(VP_WINDOW_H, len(h))),
        "note": "high-volume nodes = where price spent time, not where it must turn",
    }
