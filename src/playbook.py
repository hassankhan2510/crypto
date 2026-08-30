"""Risk map -- what the conditions are, what they cost, and when to stand aside.

This used to emit `side: "long-watch"` / `"short-watch"` with a trigger, a target,
an invalidation and an R:R. Strip the hedging words and that is a trade call: the
exact thing CONTEXT.md section 10 forbids, and the thing the whole product claims
not to sell. Worse, its "invalidation" was the fabricated liquidation level and
its "target" was the nearest high-volume bin, so the R:R was a confident-looking
number computed from two made-up inputs.

So the direction scenarios are gone. What replaces them is the thing a trader
actually needs and nobody else publishes: is the expected move big enough to pay
for the round trip, at which horizon, and in which hours.
"""
from config import HORIZONS, PRIMARY_HORIZON
from src import cost


def build(rep):
    v = rep.get("vol")
    if not v:
        return None

    gate = v.get("headline_gate") or {}
    reg, exp = v.get("regime"), v.get("expansion")
    label = v.get("headline_label", "?")
    move = v.get("move_pct")

    # ---- headline: cost first, regime second ----
    if not gate or gate.get("state") == "DEAD":
        headline = ("🚫 No tradeable horizon — every forecast window we publish is "
                    "smaller than what a round trip costs. Stand aside.")
    elif gate.get("state") == "THIN":
        headline = (f"🟠 Marginal — best horizon {label} (±{move:.2f}%), only "
                    f"{gate['ratio']:.1f}x the round trip. Fees decide the outcome, not the move.")
    elif reg == "CALM" and exp == "CONTRACTING":
        headline = (f"😴 Compressed — {label} window clears costs ({gate['ratio']:.1f}x) "
                    f"but vol is contracting. Patience beats forcing it.")
    elif reg == "STORM":
        headline = (f"⚡ High-risk — {label} ±{move:.2f}% ({gate['ratio']:.1f}x costs). "
                    f"Size DOWN, widen stops, or stay out.")
    else:
        headline = (f"🟡 Tradeable — best horizon {label} ±{move:.2f}% "
                    f"({gate['ratio']:.1f}x the round trip).")

    # ---- when: the clock, from the measured hour profile ----
    timing = []
    if v.get("season_now") is not None:
        f = v["season_now"]
        timing.append(
            f"this hour runs {f:.2f}x the coin's average variance "
            f"({'busier' if f >= 1 else 'quieter'} than normal)")
    if v.get("season_peak_h") is not None:
        timing.append(f"busiest {v['season_peak_h']:02d}:00 UTC, deadest {v['season_trough_h']:02d}:00 UTC"
                      + (f" ({v['season_ratio']:.2f}x spread)" if v.get("season_ratio") else ""))

    # ---- positioning CONTEXT, explicitly not a direction call ----
    ctx = []
    t = rep.get("top_ls")
    if t:
        ctx.append(f"top traders {'net long' if t > 1.2 else 'net short' if t < 0.8 else 'balanced'} ({t:.2f})")
    if rep.get("funding") is not None:
        ctx.append(f"funding {rep.get('fund_flag', '')}")
    of = rep.get("of") or {}
    if of.get("cvd_1h_pctile") is not None:
        ctx.append(f"1h aggressor lean at {of['cvd_1h_pctile']:.0f}th pctile of its 30d range")

    # ---- zones: descriptive only, no targets, no R:R ----
    vp = rep.get("vp") or {}
    zones = {k: vp.get(k) for k in ("poc", "val", "vah", "hvn_above", "hvn_below")}

    # ---- the risk that IS real: crowding + expansion ----
    risks = []
    fr, oi = rep.get("funding"), rep.get("oi_chg")
    if fr is not None and oi is not None and abs(fr) > 0.0005 and oi > 5.0:
        risks.append(f"crowded {'longs' if fr > 0 else 'shorts'} + rising OI → violent unwind possible")
    if exp == "EXPANDING":
        risks.append("volatility expanding — the range is opening, direction unknown")
    if v.get("regime_pctile", 0) >= 70 and not v.get("regime_anchored"):
        risks.append("high percentile but absolutely small move — a busy-looking dead tape")

    return {"headline": headline, "context": ctx, "timing": timing, "zones": zones,
            "risks": risks, "cost_table": v.get("cost_table", []),
            "expected_move_pct": move, "horizon": label,
            "cost_state": gate.get("state"), "cost_ratio": gate.get("ratio")}


def to_text(pb):
    if not pb:
        return ""
    lines = [pb["headline"]]
    if pb.get("timing"):
        lines.append("When: " + "; ".join(pb["timing"]))
    if pb.get("context"):
        lines.append("Context: " + ", ".join(pb["context"]))
    z = pb.get("zones") or {}
    if z.get("poc"):
        lines.append(f"Zones: POC {z['poc']:,.0f} · value {z.get('val'):,.0f}-{z.get('vah'):,.0f}"
                     if z.get("val") and z.get("vah") else f"Zones: POC {z['poc']:,.0f}")
    for c in pb.get("cost_table", []):
        lines.append(f"• {c['label']:>4}  ±{c['move_pct']:.2f}%  {c['ratio']:5.1f}x cost  [{c['state']}]")
    for r in pb.get("risks", []):
        lines.append(f"⚠ {r}")
    return "\n".join(lines)
