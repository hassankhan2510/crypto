"""Market factor + idiosyncratic residual.

Measured 2026-08-30 on 2 years of hourly returns:

    corr(BTC, ETH) = 0.82    corr(BTC, SOL) = 0.77    corr(ETH, SOL) = 0.79
    BTC explains 67% of ETH variance and 60% of SOL variance
    ETH beta 1.21 · SOL beta 1.34

So reporting six coins independently reports roughly one and a half coins of
information, and "MARKET: RISK-OFF, 4 of 6 in STORM" is one observation counted
four times.

This module splits each coin into:
    return = beta * BTC + residual

The residual is the only part that is genuinely about that coin. When residual
vol is high, something coin-specific is happening and trading SOL instead of BTC
carries information. When it is low, you are trading BTC with extra leverage and
extra fees -- which is worth being told.
"""
import numpy as np, pandas as pd
from config import FACTOR_COIN


def _aligned_returns(frames, bars=720):
    """Hourly (or native-bar) log returns for every coin, aligned on time."""
    cols = {}
    for coin, df in frames.items():
        if df is None or len(df) < 100:
            continue
        c = df["c"].astype(float).tail(bars)
        cols[coin] = np.log(c / c.shift(1))
    if len(cols) < 2:
        return None
    return pd.DataFrame(cols).dropna()


def decompose(frames, bars=720):
    """Beta / R2 / residual-vol per coin against the factor coin.

    frames = {coin: hourly OHLCV frame}
    Returns {coin: {...}} plus a "_factor" entry describing the market itself.
    """
    R = _aligned_returns(frames, bars)
    if R is None or FACTOR_COIN not in R.columns or len(R) < 100:
        return None

    f = R[FACTOR_COIN].to_numpy()
    fvar = float(f.var())
    out = {"_factor": {"coin": FACTOR_COIN, "n_bars": int(len(R)),
                       "vol_pct": float(f.std() * 100)}}

    for coin in R.columns:
        y = R[coin].to_numpy()
        if coin == FACTOR_COIN:
            out[coin] = {"beta": 1.0, "r2_vs_factor": 1.0, "resid_vol_pct": 0.0,
                         "idio_share": 0.0, "is_factor": True,
                         "note": "this IS the market factor"}
            continue
        beta = float(np.cov(y, f)[0, 1] / fvar) if fvar > 0 else 0.0
        resid = y - beta * f
        r2 = float(np.corrcoef(y, f)[0, 1] ** 2)
        idio = float(resid.var() / y.var()) if y.var() > 0 else 0.0
        # is today's residual unusual for this coin?
        rs = pd.Series(resid)
        cur = float(rs.tail(24).std())
        hist = rs.rolling(24).std().dropna()
        pctile = float((hist < cur).mean() * 100) if len(hist) > 50 else None
        out[coin] = {
            "beta": beta, "r2_vs_factor": r2, "resid_vol_pct": float(resid.std() * 100),
            "idio_share": idio, "resid_pctile": pctile, "is_factor": False,
            "coin_specific": bool(pctile is not None and pctile >= 70),
            "note": (f"{r2*100:.0f}% of its moves are just {FACTOR_COIN} "
                     f"(beta {beta:.2f}); {idio*100:.0f}% is its own"),
        }
    return out


def market_summary(reports, dec):
    """One honest market line, de-duplicated for the factor structure.

    The old version counted six correlated coins as six votes. This counts the
    factor once, then reports how many coins are doing something of their own.
    """
    vols = [r for r in reports if r.get("vol")]
    if not vols:
        return None

    fac = next((r for r in vols if r["coin"] == FACTOR_COIN), None)
    base = fac or vols[0]
    v = base["vol"]
    gate = v.get("headline_gate") or {}

    specific = []
    if dec:
        specific = [r["coin"] for r in vols
                    if dec.get(r["coin"], {}).get("coin_specific")]

    tradeable = [r["coin"] for r in vols
                 if (r["vol"].get("headline_gate") or {}).get("state") == "OK"]
    # day trading is only on the table if a sub-daily horizon clears the toll
    intraday = [f"{r['coin']} ({r['vol']['intraday_tradeable']})" for r in vols
                if r["vol"].get("intraday_tradeable")]

    if gate.get("state") == "DEAD":
        risk = "DEAD"
        note = (f"{base['coin']} sets the tape and its best horizon does not clear costs. "
                f"Nothing to do — this is a fee-donation regime.")
    elif v.get("regime") == "STORM":
        risk = "RISK-OFF"
        note = (f"{base['coin']} is in a genuine high-vol regime "
                f"({v['regime_pctile']:.0f}th pctile, {gate.get('ratio', 0):.1f}x costs). "
                f"Cut size — the whole complex moves together.")
    elif v.get("regime") == "CALM" and v.get("expansion") == "CONTRACTING":
        risk = "QUIET"
        note = (f"{base['coin']} is compressed. Low opportunity; a move usually follows "
                f"the quiet, so be ready rather than early.")
    else:
        risk = "MIXED"
        note = f"{base['coin']} in a normal regime. Be selective."

    if specific:
        note += (f" Coin-specific action right now in {', '.join(specific)} "
                 f"(residual vol in its own top 30%) — those are the only names "
                 f"not just tracking {FACTOR_COIN}.")
    else:
        note += f" No coin is doing anything independent of {FACTOR_COIN} right now."

    if intraday:
        note += f" Intraday viable: {', '.join(intraday)}."
    else:
        note += " No coin has a sub-daily horizon that clears costs — day trading is off today."

    return {"risk": risk, "note": note, "n": len(vols), "intraday": intraday,
            "factor": base["coin"], "factor_regime": v.get("regime"),
            "factor_move": v.get("move_pct"), "factor_horizon": v.get("headline_label"),
            "coin_specific": specific, "tradeable": tradeable,
            "avg_move": sum(r["vol"]["move_pct"] for r in vols if r["vol"].get("move_pct")) / len(vols)}
