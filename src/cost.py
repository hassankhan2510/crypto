"""Round-trip cost, and the gate that decides whether a horizon is tradeable.

This is the module the product was missing entirely. Measured over 2 years of
hourly data (2026-08-30), Binance spot taker round-trip (0.15%) as a share of the
MEAN ABSOLUTE MOVE:

    horizon    BTC      ETH      SOL
    30m        67.6%    46.0%    37.7%
    1h         47.8%    32.5%    26.6%
    4h         23.8%    15.8%    13.3%
    8h         16.5%    10.8%     9.2%

A forecast of the range is useless if the range does not clear the toll. Every
horizon we publish now carries its cost ratio, and the verdict is driven by it.
"""
from config import (FEE_TAKER_BPS, FEE_MAKER_BPS, SLIP_BPS, EXEC_STYLE,
                    COST_MULT_GO, COST_MULT_MARGINAL)


def round_trip_bps(style=None):
    """Round-trip cost in basis points (both sides, fee + slippage)."""
    style = (style or EXEC_STYLE).lower()
    fee = FEE_MAKER_BPS if style == "maker" else FEE_TAKER_BPS
    return 2.0 * (fee + SLIP_BPS)


def round_trip_pct(style=None):
    return round_trip_bps(style) / 100.0


def gate(move_pct, style=None):
    """Grade one horizon's expected move against what a round trip costs.

    move_pct = expected 1-sigma move in PERCENT over that horizon.
    Returns a dict with the ratio, a verdict and a plain sentence.
    """
    if move_pct is None or move_pct <= 0:
        return None
    cost = round_trip_pct(style)
    ratio = move_pct / cost if cost > 0 else float("inf")
    if ratio >= COST_MULT_GO:
        state, note = "OK", f"expected move is {ratio:.1f}x the round trip"
    elif ratio >= COST_MULT_MARGINAL:
        state, note = "THIN", f"expected move is only {ratio:.1f}x the round trip -- marginal"
    else:
        state, note = "DEAD", f"costs eat {100/ratio:.0f}% of the expected move -- do not trade this horizon"
    return {"cost_pct": cost, "ratio": ratio, "state": state, "note": note,
            "style": (style or EXEC_STYLE).lower()}


def best_horizon(vol, horizons):
    """The shortest horizon whose expected move actually clears the cost gate.

    vol       = the dict from volatility.analyze()
    horizons  = config.HORIZONS
    Returns (key, label, gate_dict) or None if nothing clears.
    """
    for key, _interval, _n, label in horizons:
        mv = (vol or {}).get(f"{key}_pct")
        g = gate(mv)
        if g and g["state"] == "OK":
            return key, label, g
    return None


def summary(vol, horizons):
    """Per-horizon cost table for the report."""
    out = []
    for key, _interval, _n, label in horizons:
        mv = (vol or {}).get(f"{key}_pct")
        g = gate(mv)
        if g:
            out.append({"key": key, "label": label, "move_pct": mv, **g})
    return out
