"""The differentiator: a VALIDATED HAR volatility forecast (our Paper 2).
Everyone else shows current CVD/vol; we forecast the NEXT 24h expected range,
plus regime (calm/normal/storm) and expansion state -- the one thing that is
actually predictable out-of-sample."""
import numpy as np, pandas as pd
from config import (HAR_LOOKBACKS_H, FWD_H, REGIME_WIN_H, STORM_PCTILE,
                    CALM_PCTILE, EXPANSION_EMA_H, EXPANSION_MULT)

def analyze(hourly):
    """hourly: DataFrame with 'c'. Returns vol/regime dict."""
    c = hourly["c"].astype(float)
    r = np.log(c / c.shift(1))
    r2 = r.pow(2)
    w1, w2, w3 = HAR_LOOKBACKS_H

    def RV(w): return r2.rolling(w).sum().pow(0.5)      # realized vol over w bars (return units)
    rv1, rv2, rv3 = RV(w1), RV(w2), RV(w3)
    y = r2.rolling(FWD_H).sum().shift(-FWD_H).pow(0.5)   # forward realized vol (next FWD_H)

    d = pd.DataFrame({"rv1": rv1, "rv2": rv2, "rv3": rv3, "y": y}).dropna()
    if len(d) < 100:
        return None
    X = np.column_stack([np.ones(len(d)), d["rv1"], d["rv2"], d["rv3"]])
    beta, *_ = np.linalg.lstsq(X, d["y"].values, rcond=None)
    pred = X @ beta
    ss_res = np.sum((d["y"].values - pred) ** 2)
    ss_tot = np.sum((d["y"].values - d["y"].mean()) ** 2)
    r2_fit = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # live forecast: newest bar's features (target unknown)
    xr1, xr2, xr3 = rv1.iloc[-1], rv2.iloc[-1], rv3.iloc[-1]
    if np.isnan([xr1, xr2, xr3]).any():
        return None
    fc = float(beta @ np.array([1, xr1, xr2, xr3]))
    fc = max(fc, 1e-6)
    move_pct = fc * 100                                  # ~1σ move over next FWD_H, %
    price = float(c.iloc[-1])
    lo = price * np.exp(-fc); hi = price * np.exp(+fc)   # ±1σ expected range

    # regime = where current short-vol sits vs its own recent history
    hist = rv1.dropna().iloc[-REGIME_WIN_H:]
    pr = float((hist < rv1.iloc[-1]).mean() * 100) if len(hist) > 50 else 50.0
    regime = "STORM" if pr >= STORM_PCTILE else "CALM" if pr <= CALM_PCTILE else "NORMAL"

    ema = rv1.ewm(span=EXPANSION_EMA_H).mean().iloc[-1]
    if rv1.iloc[-1] > ema * EXPANSION_MULT: expansion = "EXPANDING"
    elif rv1.iloc[-1] < ema / EXPANSION_MULT: expansion = "CONTRACTING"
    else: expansion = "STEADY"

    conf = "HIGH" if r2_fit >= 0.30 else "MED" if r2_fit >= 0.12 else "LOW"
    return {"move_pct": move_pct, "range_lo": lo, "range_hi": hi,
            "regime": regime, "regime_pctile": pr, "expansion": expansion,
            "fit_r2": r2_fit, "confidence": conf}
