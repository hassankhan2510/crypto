"""Scenario Playbook — turns metrics into an actionable IF-THEN risk map.
Honest by design: we give BOTH sides (up-scenario and down-scenario) with key
zones, invalidation, expected reach and R:R. It's a risk map a trader acts on
with their own discretion — never a 'buy now' call."""

def _rr(entry, target, stop):
    try:
        risk = abs(entry - stop); reward = abs(target - entry)
        return round(reward / risk, 1) if risk > 0 else None
    except Exception:
        return None

def build(rep):
    v = rep["vol"]
    if not v:
        return None
    price = rep["price"]; vp = rep.get("vp") or {}; L = rep.get("levels") or {}
    reg, move = v["regime"], v["move_pct"]
    sup = vp.get("support"); res = vp.get("resistance"); poc = vp.get("poc")
    long_liq = (L.get("long_liq") or [None])[0]      # nearest est. long-liq (below)
    short_liq = (L.get("short_liq") or [None])[0]    # nearest est. short-liq (above)

    # ---- bias CONTEXT (positioning) — not a direction call ----
    ctx = []
    t = rep.get("top_ls")
    if t: ctx.append(f"top traders {'net long' if t>1.2 else 'net short' if t<0.8 else 'balanced'} ({t:.2f})")
    if rep.get("funding") is not None: ctx.append(f"funding {rep.get('fund_flag','')}")
    ag = rep.get("agg") or {}
    if ag.get("venues"): ctx.append(f"flow {'buyers' if ag['agg_pct']>3 else 'sellers' if ag['agg_pct']<-3 else 'balanced'}")

    scenarios = []
    if reg == "CALM" and v["expansion"] == "CONTRACTING":
        headline = "😴 No setup — compressed/quiet. Stand aside; a move usually follows the quiet."
    else:
        headline = f"{'⚡ High-risk — size down, wider stops' if reg=='STORM' else '🟡 Normal conditions'} · expected ±{move:.1f}% (24h)"
        # UP scenario
        if sup and res:
            stop = long_liq if (long_liq and long_liq < sup) else round(sup * 0.995, 2)
            scenarios.append({
                "side": "long-watch",
                "trigger": f"holds/reclaims support {sup:,.0f}",
                "target": f"{res:,.0f}",
                "invalidation": f"{stop:,.0f}",
                "rr": _rr(sup, res, stop),
                "note": "lower-risk long zone if buyers defend"})
            # DOWN scenario
            stop2 = short_liq if (short_liq and short_liq > res) else round(res * 1.005, 2)
            scenarios.append({
                "side": "short-watch",
                "trigger": f"rejects resistance {res:,.0f}",
                "target": f"{sup:,.0f}",
                "invalidation": f"{stop2:,.0f}",
                "rr": _rr(res, sup, stop2),
                "note": "pressure back toward support if sellers cap it"})
        # cascade warning
        if long_liq:
            scenarios.append({
                "side": "risk",
                "trigger": f"break below {long_liq:,.0f}",
                "target": "next liq cluster", "invalidation": "-", "rr": None,
                "note": "long-liquidation cascade risk (fast move down)"})

    return {"headline": headline, "context": ctx, "poc": poc,
            "support": sup, "resistance": res,
            "long_liq": long_liq, "short_liq": short_liq,
            "expected_move_pct": move, "scenarios": scenarios}

def to_text(pb):
    if not pb: return ""
    lines = [pb["headline"]]
    if pb["context"]: lines.append("Context: " + ", ".join(pb["context"]))
    if pb.get("support") and pb.get("resistance"):
        lines.append(f"Zones: sup {pb['support']:,.0f} · res {pb['resistance']:,.0f}" +
                     (f" · liq↓ {pb['long_liq']:,.0f}" if pb.get('long_liq') else "") +
                     (f" · liq↑ {pb['short_liq']:,.0f}" if pb.get('short_liq') else ""))
    for s in pb["scenarios"]:
        rr = f" (R:R {s['rr']})" if s.get("rr") else ""
        lines.append(f"• If {s['trigger']} → {s['target']}{rr} — {s['note']} [inval {s['invalidation']}]")
    return "\n".join(lines)
