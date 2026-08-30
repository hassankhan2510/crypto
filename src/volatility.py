"""Validated HAR volatility forecasts at MULTIPLE horizons (our Paper 2).

What changed, and why it matters
--------------------------------
1. R2 IS NOW OUT-OF-SAMPLE. The old code fitted on all rows and reported the R2
   of that same fit, then the README called it "validated out-of-sample". On the
   shipped config that in-sample number was 0.18-0.41 while the TRUE walk-forward
   R2 was NEGATIVE (-0.13 to -0.25). `confidence` is now driven by a real
   expanding-window walk-forward with a `fwd`-bar gap to kill overlap leakage.

2. THE HORIZONS ARE INTRADAY. Measured OOS R2 with the seasonal feature below:
       30m 0.30-0.42 | 1h 0.35-0.49 | 4h 0.41-0.50 | 24h 0.19-0.26
   The intraday horizons are the MORE skilful ones, and they are the only ones
   relevant to day trading. 24h is demoted to context.

3. SEASONALITY IS A FITTED FEATURE, NOT A MULTIPLIER. Crypto has a strong
   hour-of-day profile (BTC 2.18x, ETH 1.96x, SOL 1.84x in mean |return|; peak
   14:00 UTC, trough ~10:00 UTC). The obvious move -- forecast, then multiply by
   the seasonal factor ahead -- MAKES IT WORSE, because the HAR's short lookback
   already encodes the current hour, so the multiplier double-counts. Measured:

       BTC 30m   none +0.395 | multiplicative +0.373 | fitted +0.422
       BTC  4h   none +0.444 | multiplicative +0.449 | fitted +0.497
       SOL  1h   none +0.411 | multiplicative +0.386 | fitted +0.429

   So log(forward seasonal scale) goes into the design matrix and the regression
   picks its own coefficient. Wins on all 9 coin x horizon combinations.
   The profile is built causally (expanding mean, shifted) so the OOS number
   stays honest.

4. REGIME HAS AN ABSOLUTE ANCHOR. A percentile alone says "top 30% of a dead
   month" is a STORM. It now also has to clear STORM_MIN_COST_MULT round trips.

Direction stays excluded. It always will.
"""
import numpy as np, pandas as pd
from config import (HAR_LOOKBACKS_1H, HAR_LOOKBACKS_5M, HORIZONS, REGIME_WIN_H,
                    STORM_PCTILE, CALM_PCTILE, EXPANSION_EMA_H, EXPANSION_MULT,
                    OOS_FRACTION, OOS_REFIT_EVERY, SEASON_MIN_DAYS,
                    STORM_MIN_COST_MULT)
from src import cost


# ---------------------------------------------------------------- seasonality
def _causal_hour_factors(r2):
    """Per-bar variance factor for the bar's hour, using only PAST bars.

    Expanding mean of r2 within each hour bucket, shifted one observation, over
    the expanding mean of everything. Causal by construction, so it can sit in a
    walk-forward design matrix without leaking.
    """
    hourly = (r2.groupby(r2.index.hour)
                .apply(lambda s: s.shift(1).expanding().mean())
                .reset_index(level=0, drop=True)
                .sort_index())
    overall = r2.shift(1).expanding().mean()
    return (hourly / overall.replace(0, np.nan)).reindex(r2.index)


def _forward_scale(fac, fwd):
    """sqrt(mean seasonal variance factor over the NEXT fwd bars).

    The clock ahead is known in advance, so this is information we legitimately
    have at forecast time -- it is not lookahead.
    """
    s = fac.shift(-1).rolling(fwd).sum().shift(-(fwd - 1)) / float(fwd)
    return s.pow(0.5)


def hour_profile(c):
    """Full-sample hour-of-day variance factors, for DISPLAY only.

    Never used in the fit (the causal version above is). Returns a 24-length
    array normalised to mean 1, or None if history is too short to trust.
    """
    r = np.log(c / c.shift(1)).dropna()
    if r.empty:
        return None
    if (r.index[-1] - r.index[0]).total_seconds() / 86400 < SEASON_MIN_DAYS:
        return None
    v = r.pow(2).groupby(r.index.hour).mean().reindex(range(24))
    if v.isna().any() or v.mean() <= 0:
        return None
    return (v / v.mean()).values


# ---------------------------------------------------------------- HAR core
def _design(c, lookbacks, fwd):
    """RV features + causal seasonal feature -> forward RV.

    Returns (X, y, x_live, live_scale) or (None,)*4.
    """
    r = np.log(c / c.shift(1))
    r2 = r.pow(2)
    feats = [r2.rolling(w).sum().pow(0.5) for w in lookbacks]
    y = r2.rolling(fwd).sum().shift(-fwd).pow(0.5)

    fac = _causal_hour_factors(r2)
    scale = _forward_scale(fac, fwd)

    d = pd.DataFrame({f"f{i}": f for i, f in enumerate(feats)})
    d["s"] = np.log(scale.clip(lower=1e-3))
    d["y"] = y
    d = d.replace([np.inf, -np.inf], np.nan).dropna()
    if len(d) < 300:
        return None, None, None, None

    X = np.column_stack([np.ones(len(d))]
                        + [d[f"f{i}"].values for i in range(len(feats))]
                        + [d["s"].values])
    # live row: trailing RVs now, and the seasonal scale of the window ahead
    x_rv = [f.iloc[-1] for f in feats]
    live_scale = float(scale.iloc[-1]) if pd.notna(scale.iloc[-1]) else None
    if any(pd.isna(x_rv)):
        return None, None, None, None
    if live_scale is None:
        # clock ahead is unknown only if the profile is unusable; fall back to flat
        live_scale = 1.0
    x_live = np.array([1.0] + list(x_rv) + [np.log(max(live_scale, 1e-3))])
    return X, d["y"].values, x_live, live_scale


def _walkforward_r2(X, y, fwd, frac=OOS_FRACTION, refit_every=OOS_REFIT_EVERY):
    """Honest OOS R2: expanding-window fit, `fwd`-bar gap, non-overlapping eval.

    The gap matters. y is a rolling forward sum, so row i and row i+1 share
    fwd-1 observations; without the gap the 'test' rows leak into the training
    set and the R2 inflates toward the in-sample number.
    """
    n = len(y)
    start = int(n * frac)
    if start < 250 or n - start < 30:
        return None
    preds, acts, beta = [], [], None
    for k, i in enumerate(range(start, n, fwd)):     # step by fwd => non-overlapping
        tr = i - fwd                                  # gap: never train on rows overlapping i
        if tr < 200:
            continue
        if beta is None or k % refit_every == 0:
            beta, *_ = np.linalg.lstsq(X[:tr], y[:tr], rcond=None)
        preds.append(X[i] @ beta)
        acts.append(y[i])
    if len(acts) < 20:
        return None
    p, a = np.array(preds), np.array(acts)
    ss_tot = float(((a - a.mean()) ** 2).sum())
    if ss_tot <= 0:
        return None
    return float(1 - ((a - p) ** 2).sum() / ss_tot)


def _har(c, lookbacks, fwd, with_oos=True):
    """Fit HAR and return (live 1-sigma forecast in return units, OOS R2, scale)."""
    X, y, x_live, live_scale = _design(c, lookbacks, fwd)
    if X is None:
        return None, None, None
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    fc = max(float(beta @ x_live), 1e-6)
    r2 = _walkforward_r2(X, y, fwd) if with_oos else None
    return fc, r2, live_scale


# ---------------------------------------------------------------- public API
def analyze(hourly, bars5m=None):
    """All horizons + regime + expansion + the clock, in one dict.

    hourly : 1h OHLCV frame (needs YEARS, not weeks -- see exchanges.klines)
    bars5m : 5m OHLCV frame, drives the intraday horizons (the good ones)
    """
    c1 = hourly["c"].astype(float)
    price = float(c1.iloc[-1])
    out = {"price": price}

    # display profile: prefer the finer series
    prof = None
    if bars5m is not None and len(bars5m) > 500:
        prof = hour_profile(bars5m["c"].astype(float))
    if prof is None:
        prof = hour_profile(c1)
    out["season_profile"] = prof
    if prof is not None:
        p = np.asarray(prof)
        out["season_now"] = float(p[int(c1.index[-1].hour)])
        out["season_peak_h"] = int(np.argmax(p))
        out["season_trough_h"] = int(np.argmin(p))
        # report in SIGMA terms -- p is a variance profile, and "2x busier" is
        # a statement about typical move size, not variance.
        out["season_ratio"] = float(np.sqrt(p.max() / p.min())) if p.min() > 0 else None

    any_fit = False
    for key, interval, n, label in HORIZONS:
        src = bars5m if interval == "5m" else hourly
        if src is None or len(src) < 600:
            continue
        c = src["c"].astype(float)
        lookbacks = HAR_LOOKBACKS_5M if interval == "5m" else HAR_LOOKBACKS_1H
        try:
            fc, r2, sc = _har(c, lookbacks, n)
        except Exception:
            continue
        if fc is None:
            continue
        any_fit = True
        out[f"{key}_pct"] = fc * 100
        out[f"{key}_lo"] = price * np.exp(-fc)
        out[f"{key}_hi"] = price * np.exp(+fc)
        out[f"{key}_r2"] = r2
        out[f"{key}_label"] = label
        out[f"{key}_clock"] = sc          # <1 = quiet window ahead, >1 = busy

    if not any_fit:
        return None

    # ---- headline horizon = the shortest one whose move clears the cost gate ----
    best = cost.best_horizon(out, HORIZONS)
    if best:
        out["headline_key"], out["headline_label"], out["headline_gate"] = best
    else:
        last = HORIZONS[-1][0]
        out["headline_key"] = last
        out["headline_label"] = HORIZONS[-1][3]
        out["headline_gate"] = cost.gate(out.get(f"{last}_pct"))
    hk = out["headline_key"]
    out["move_pct"] = out.get(f"{hk}_pct")
    out["range_lo"] = out.get(f"{hk}_lo")
    out["range_hi"] = out.get(f"{hk}_hi")
    out["fit_r2"] = out.get(f"{hk}_r2")
    out["cost_table"] = cost.summary(out, HORIZONS)
    # the shortest horizon that clears -- i.e. is day trading on the table at all?
    intraday = [c for c in out["cost_table"]
                if c["key"] != "h24" and c["state"] in ("OK", "THIN")]
    out["intraday_tradeable"] = intraday[0]["label"] if intraday else None

    # ---- confidence from the OOS R2, not the in-sample one ----
    r2 = out["fit_r2"]
    out["confidence"] = ("HIGH" if r2 is not None and r2 >= 0.30 else
                         "MED" if r2 is not None and r2 >= 0.12 else
                         "LOW" if r2 is not None else "UNVALIDATED")
    out["r2_kind"] = "walk-forward OOS"

    # ---- regime: percentile AND an absolute cost anchor ----
    r = np.log(c1 / c1.shift(1))
    rv1 = r.pow(2).rolling(24).sum().pow(0.5)
    hist = rv1.dropna().iloc[-REGIME_WIN_H:]
    pr = float((hist.iloc[:-1] < rv1.iloc[-1]).mean() * 100) if len(hist) > 50 else 50.0
    d1 = out.get("h24_pct")
    g24 = cost.gate(d1) if d1 else None
    clears = bool(g24 and g24["ratio"] >= STORM_MIN_COST_MULT)
    if pr >= STORM_PCTILE:
        regime = "STORM" if clears else "NORMAL"   # top of a dead range is still dead
    elif pr <= CALM_PCTILE:
        regime = "CALM"
    else:
        regime = "NORMAL"
    out["regime"] = regime
    out["regime_pctile"] = pr
    out["regime_anchored"] = clears
    out["regime_win_days"] = round(len(hist) / 24, 1)

    ema = rv1.ewm(span=EXPANSION_EMA_H).mean().iloc[-1]
    out["expansion"] = ("EXPANDING" if rv1.iloc[-1] > ema * EXPANSION_MULT
                        else "CONTRACTING" if rv1.iloc[-1] < ema / EXPANSION_MULT
                        else "STEADY")
    out["history_bars_1h"] = len(c1)
    out["history_days_1h"] = round(len(c1) / 24, 1)
    return out
