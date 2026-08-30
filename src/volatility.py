"""Validated HAR volatility forecasts at MULTIPLE horizons (our Paper 2).
 - 24h forecast + regime/expansion  from hourly bars  (analyze)
 - 30m and 1h forecasts             from 5-minute bars (multi_short)
Everyone else shows current vol; we forecast the expected range ahead — the one
thing that's actually predictable out-of-sample. Direction stays excluded."""
import numpy as np, pandas as pd
from config import (HAR_LOOKBACKS_H, FWD_H, REGIME_WIN_H, STORM_PCTILE,
                    CALM_PCTILE, EXPANSION_EMA_H, EXPANSION_MULT)

def _har(c, lookbacks, fwd):
    """Fit HAR (RV over lookbacks -> forward RV) and return the live 1σ forecast
    in return units. c = close price Series. Returns (forecast, in_sample_R2)."""
    r = np.log(c / c.shift(1)); r2 = r.pow(2)
    feats = [r2.rolling(w).sum().pow(0.5) for w in lookbacks]
    y = r2.rolling(fwd).sum().shift(-fwd).pow(0.5)
    d = pd.DataFrame({f"f{i}": f for i, f in enumerate(feats)}); d["y"] = y
    d = d.dropna()
    if len(d) < 80:
        return None, None
    X = np.column_stack([np.ones(len(d))] + [d[f"f{i}"].values for i in range(len(feats))])
    beta, *_ = np.linalg.lstsq(X, d["y"].values, rcond=None)
    pred = X @ beta
    ss_res = float(np.sum((d["y"].values - pred) ** 2))
    ss_tot = float(np.sum((d["y"].values - d["y"].mean()) ** 2))
    r2fit = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    xr = [f.iloc[-1] for f in feats]
    if any(pd.isna(xr)):
        return None, None
    fc = max(float(beta @ np.array([1.0] + list(xr))), 1e-6)
    return fc, r2fit

def analyze(hourly):
    """24h forecast + regime + expansion from hourly bars."""
    c = hourly["c"].astype(float)
    fc, r2fit = _har(c, HAR_LOOKBACKS_H, FWD_H)
    if fc is None:
        return None
    price = float(c.iloc[-1])
    move_pct = fc * 100
    lo, hi = price * np.exp(-fc), price * np.exp(+fc)

    r = np.log(c / c.shift(1)); rv1 = r.pow(2).rolling(HAR_LOOKBACKS_H[0]).sum().pow(0.5)
    hist = rv1.dropna().iloc[-REGIME_WIN_H:]
    pr = float((hist < rv1.iloc[-1]).mean() * 100) if len(hist) > 50 else 50.0
    regime = "STORM" if pr >= STORM_PCTILE else "CALM" if pr <= CALM_PCTILE else "NORMAL"
    ema = rv1.ewm(span=EXPANSION_EMA_H).mean().iloc[-1]
    expansion = ("EXPANDING" if rv1.iloc[-1] > ema * EXPANSION_MULT
                 else "CONTRACTING" if rv1.iloc[-1] < ema / EXPANSION_MULT else "STEADY")
    conf = "HIGH" if r2fit >= 0.30 else "MED" if r2fit >= 0.12 else "LOW"
    return {"move_pct": move_pct, "range_lo": lo, "range_hi": hi,
            "regime": regime, "regime_pctile": pr, "expansion": expansion,
            "fit_r2": r2fit, "confidence": conf}

def multi_short(c5):
    """30m and 1h forecasts from 5-minute closes. Lookbacks = 1h/6h/24h in 5m bars."""
    c5 = pd.Series(c5).astype(float)
    price = float(c5.iloc[-1])
    out = {}
    for key, fwd in (("m30", 6), ("h1", 12)):     # 6x5m=30m, 12x5m=1h
        fc, _ = _har(c5, (12, 72, 288), fwd)
        if fc is not None:
            out[key + "_pct"] = fc * 100
            out[key + "_lo"] = price * np.exp(-fc)
            out[key + "_hi"] = price * np.exp(+fc)
    return out or None
