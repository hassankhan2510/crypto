"""Combine everything into a per-coin report that speaks BOTH languages:
  🟢 IN PLAIN WORDS  — a normal person understands what's happening & what it means
  📊 FOR THE TRADER  — the metrics a 10-yr trader wants, each with its real window
Plus an honest risk VERDICT, led by cost. Never buy/sell direction.
"""
from config import FUNDING_EXTREME, OI_BUILD_PCT, FACTOR_COIN


# ---------------------------------------------------------------- per coin
def build_report(coin, spot24, vol, of, agg, vp, wr, deriv, xprice, mvol, vpin_v, fac=None):
    price = spot24["price"]
    prices = [p for p in [price, xprice.get("coinbase"), xprice.get("okx")] if p]
    spread_bp = (max(prices) - min(prices)) / price * 1e4 if len(prices) > 1 else 0.0
    fr, oi, ls = deriv.get("funding"), deriv.get("oi_chg"), deriv.get("long_short")
    top_ls, taker_ls, liq = deriv.get("top_ls"), deriv.get("taker_ls"), deriv.get("liq")

    fund_flag = ""
    if fr is not None:
        fund_flag = ("crowded longs" if fr > FUNDING_EXTREME else
                     "crowded shorts" if fr < -FUNDING_EXTREME else "neutral")
    oi_flag = "" if oi is None else ("building" if oi > OI_BUILD_PCT else
                                     "unwinding" if oi < -OI_BUILD_PCT else "flat")

    plain = _plain(coin, spot24, vol, agg, wr, fr, oi, liq, fac)
    verdict, stand_aside = _verdict(vol, of, fr, oi, fac)

    return {
        "coin": coin, "price": price, "chg_pct": spot24["chg_pct"],
        "vol": vol, "of": of, "agg": agg, "vp": vp, "wr": wr, "vpin": vpin_v,
        "factor": fac,
        "funding": fr, "fund_flag": fund_flag, "oi_chg": oi, "oi_flag": oi_flag,
        "long_short": ls, "top_ls": top_ls, "taker_ls": taker_ls, "liq": liq,
        "xspread_bp": spread_bp, "n_exch": len(prices),
        "mvol": mvol,
        "plain": plain, "verdict": verdict, "stand_aside": stand_aside,
    }


def _px(x, sig=5):
    """Format a price with enough decimals to be meaningful at any magnitude.
    ':,.0f' printed DOGE's 24h range as "0-0"."""
    if x is None:
        return "n/a"
    ax = abs(float(x))
    d = 0 if ax >= 1000 else 2 if ax >= 10 else 4 if ax >= 0.1 else 6
    return f"{float(x):,.{d}f}"


def _human_usd(x):
    ax = abs(x)
    if ax >= 1e9: return f"${x/1e9:.1f}B"
    if ax >= 1e6: return f"${x/1e6:.0f}M"
    if ax >= 1e3: return f"${x/1e3:.0f}K"
    return f"${x:.0f}"


def _plain(coin, spot24, vol, agg, wr, fr, oi, liq=None, fac=None):
    chg = spot24["chg_pct"]
    move = f"{coin} is {'up' if chg >= 0 else 'down'} {abs(chg):.1f}% today."
    if not vol:
        return move

    reg = vol.get("regime")
    gate = vol.get("headline_gate") or {}
    if reg == "STORM":
        calm = "It's a **wild/high-risk** day — big swings likely."
    elif reg == "CALM":
        calm = "It's **quiet** right now — small moves, not much happening."
    else:
        calm = "It's a **normal** day for movement."

    hz = vol.get("headline_label", "the next while")
    swing = f"Over the next **{hz}** expect roughly a **±{vol.get('move_pct', 0):.2f}%** swing."

    # the honest bit almost nobody publishes
    if gate.get("state") == "DEAD":
        cost_line = (" That move is **smaller than what buying and selling costs**, so "
                     "trading it now is paying fees for nothing.")
    elif gate.get("state") == "THIN":
        cost_line = f" That's only about **{gate['ratio']:.1f}x** the cost of getting in and out — thin."
    else:
        cost_line = f" That's about **{gate.get('ratio', 0):.1f}x** the cost of getting in and out."

    who = ""
    if agg and agg.get("venues") and agg.get("agg_pct") is not None:
        a = agg["agg_pct"]
        who = (" Right now buyers are pushing harder." if a > 3
               else " Right now sellers are pushing harder." if a < -3
               else " Buyers and sellers are fairly balanced.")

    beta_line = ""
    if fac and not fac.get("is_factor") and fac.get("r2_vs_factor") is not None:
        if fac.get("coin_specific"):
            beta_line = f" Unusually, {coin} is moving on its own news today, not just following {FACTOR_COIN}."
        else:
            beta_line = f" Note: about {fac['r2_vs_factor']*100:.0f}% of {coin}'s moves are just {FACTOR_COIN} repeating."

    liq_note = ""
    if liq and (liq.get("long_liq_usd", 0) + liq.get("short_liq_usd", 0)) > 0:
        ll, sl = liq["long_liq_usd"], liq["short_liq_usd"]
        if ll > sl * 1.3:
            liq_note = f" ({_human_usd(ll)} of bullish bets got force-sold in 24h.)"
        elif sl > ll * 1.3:
            liq_note = f" ({_human_usd(sl)} of bearish bets got squeezed out in 24h.)"

    if gate.get("state") == "DEAD":
        mean = "👉 Nothing to do. The cheapest good decision today is not trading."
    elif reg == "STORM":
        mean = "👉 If you just hold, expect a bumpy ride; don't panic on a spike, and avoid big new bets into the chaos."
    elif reg == "CALM" and vol.get("expansion") == "CONTRACTING":
        mean = "👉 Calm before a possible move. Patience beats forcing a trade."
    else:
        mean = "👉 Normal conditions. Nothing urgent for a long-term holder."

    return f"{move} {calm} {swing}{cost_line}{who}{beta_line}{liq_note}\n{mean}"


def _verdict(vol, of, fr, oi, fac=None):
    """Risk verdict, led by cost. Cost is the only thing that is certain."""
    lines, stand_aside = [], False
    if not vol:
        return "No read — insufficient history.", True

    gate = vol.get("headline_gate") or {}
    reg, exp = vol.get("regime"), vol.get("expansion")
    hz, mv = vol.get("headline_label", "?"), vol.get("move_pct")

    if gate.get("state") == "DEAD" or not gate:
        lines.append(f"🚫 No tradeable horizon. Best is {hz} at ±{mv:.2f}%, and {gate.get('note', 'costs exceed it')}.")
        stand_aside = True
    elif gate.get("state") == "THIN":
        lines.append(f"🟠 Thin: {hz} ±{mv:.2f}% is {gate['ratio']:.1f}x the round trip. Fees, not the move, decide this one.")
    else:
        if reg == "STORM":
            lines.append(f"⚡ High-risk regime — {hz} ±{mv:.2f}% ({gate['ratio']:.1f}x costs). Size DOWN, wider stops, or stay out.")
        elif reg == "CALM" and exp == "CONTRACTING":
            lines.append(f"😴 Compressed — {hz} ±{mv:.2f}% clears costs ({gate['ratio']:.1f}x) but vol is contracting. Await expansion.")
            stand_aside = True
        else:
            lines.append(f"🟡 Tradeable — {hz} ±{mv:.2f}% ({gate['ratio']:.1f}x the round trip).")

    if not vol.get("intraday_tradeable"):
        lines.append("⏱️ No sub-daily horizon clears costs — this is not a day-trading tape right now.")

    if vol.get("regime_pctile", 0) >= 70 and not vol.get("regime_anchored"):
        lines.append("🪫 High percentile but absolutely small — a busy-looking dead tape. The percentile is lying to you.")

    if exp == "EXPANDING":
        lines.append("🌪️ Volatility EXPANDING — a move is opening (direction unknown). The window that matters.")

    if fr is not None and oi is not None and abs(fr) > FUNDING_EXTREME and oi > OI_BUILD_PCT:
        lines.append(f"🎯 Crowded {'longs' if fr > 0 else 'shorts'} + rising OI → squeeze risk (violent unwind possible).")

    if fac and not fac.get("is_factor") and not fac.get("coin_specific"):
        lines.append(f"🔁 {fac['note']} — trading it instead of {FACTOR_COIN} adds fees, not information.")

    r2 = vol.get("fit_r2")
    if r2 is None:
        lines.append("⚠️ Model UNVALIDATED on this history — treat the range as indicative only.")
    elif r2 < 0.05:
        lines.append(f"⚠️ Weak model here (OOS R² {r2:+.2f}) — the range is barely better than a guess.")

    return ("\n".join(lines) if lines else "No strong read."), stand_aside


# ---------------------------------------------------------------- console
def console(rep):
    v = rep["vol"] or {}
    vp = rep.get("vp") or {}
    out = [f"\n=== {rep['coin']}  ${rep['price']:,.2f}  ({rep['chg_pct']:+.2f}% 24h)"
           f"  [{rep['n_exch']} exch, spread {rep['xspread_bp']:.1f}bp] ==="]
    out.append("  PLAIN: " + rep["plain"].replace("**", "").replace("\n", "\n         "))

    if v:
        hist = f"{v.get('history_days_1h', 0):.0f}d 1h history"
        r2 = v.get("fit_r2")
        r2s = "n/a" if r2 is None else f"{r2:+.3f}"
        anchor = "" if v.get("regime_anchored") else " (NOT cost-anchored)"
        out.append(f"  VOL[{v.get('headline_label')}]: ±{v.get('move_pct', 0):.2f}% "
                   f"(range {_px(v.get('range_lo'))}-{_px(v.get('range_hi'))}) | "
                   f"{v.get('regime')} {v.get('regime_pctile', 0):.0f}%ile{anchor} | "
                   f"{v.get('expansion')} | OOS R² {r2s} ({v.get('confidence')}) | {hist}")
        rows = []
        for c in v.get("cost_table", []):
            rows.append(f"{c['label']} ±{c['move_pct']:.2f}%/{c['ratio']:.1f}x[{c['state']}]")
        if rows:
            out.append("  HORIZONS: " + "  ".join(rows))
        it = v.get("intraday_tradeable")
        out.append(f"  DAY-TRADE: {'shortest viable horizon ' + it if it else 'NO intraday horizon clears costs'}")
        if v.get("season_now") is not None:
            out.append(f"  CLOCK: this hour {v['season_now']:.2f}x avg variance | "
                       f"peak {v.get('season_peak_h'):02d}h trough {v.get('season_trough_h'):02d}h UTC"
                       f" ({v.get('season_ratio', 0):.2f}x spread)")

    of = rep.get("of") or {}
    if of:
        bits = []
        for lab in ("1h", "4h", "24h"):
            if of.get(f"cvd_{lab}_pct") is not None:
                p = of.get(f"cvd_{lab}_pctile")
                bits.append(f"{lab} {of[f'cvd_{lab}_pct']:+.1f}%"
                            + (f" ({p:.0f}%ile)" if p is not None else ""))
        if bits:
            out.append(f"  FLOW[{of.get('source')}, {of.get('history_days')}d]: " + " | ".join(bits))

    ag = rep.get("agg") or {}
    if ag.get("venues"):
        out.append(f"  TAPE: {ag['agg_pct']:+.1f}% over a common {ag['window_s']:.0f}s window "
                   f"({ag['venues']} venues{', DIVERGENT' if ag.get('divergence') else ''}) "
                   f"— snapshot, not positioning")
    vp_ = rep.get("vpin")
    if vp_:
        out.append(f"  VPIN: {vp_['vpin']:.3f}"
                   + (f" ({vp_['pctile']:.0f}%ile of {vp_['span_days']}d)" if vp_.get("pctile") is not None else ""))

    if rep["funding"] is not None:
        oi = 'n/a' if rep['oi_chg'] is None else f"{rep['oi_chg']:+.1f}%"
        top, tak = rep.get('top_ls'), rep.get('taker_ls')
        extra = (f" | topL/S {top:.2f}" if top else "") + (f" | takerB/S {tak:.2f}" if tak else "")
        out.append(f"  DERIV: funding {rep['funding']*100:+.3f}% ({rep['fund_flag']}) | "
                   f"OI {oi} {rep['oi_flag']} | L/S {rep['long_short']}{extra}")

    if rep.get("liq"):
        out.append(f"  LIQ(24h, real): longs {_human_usd(rep['liq']['long_liq_usd'])} / "
                   f"shorts {_human_usd(rep['liq']['short_liq_usd'])}")

    fac = rep.get("factor")
    if fac and not fac.get("is_factor"):
        out.append(f"  FACTOR: beta {fac['beta']:.2f} to {FACTOR_COIN} | "
                   f"R² {fac['r2_vs_factor']:.2f} | own vol {fac['idio_share']*100:.0f}%"
                   + ("  ← COIN-SPECIFIC MOVE" if fac.get("coin_specific") else ""))

    if vp.get("poc"):
        out.append(f"  LEVELS: POC {_px(vp['poc'])} | value {_px(vp.get('val'))}-{_px(vp.get('vah'))} "
                   f"| HVN {_px(vp.get('hvn_below'))}/{_px(vp.get('hvn_above'))}")

    pbk = rep.get("playbook")
    if pbk:
        out.append("  RISK MAP: " + pbk["headline"])
        if pbk.get("timing"):
            out.append("     when: " + "; ".join(pbk["timing"]))
        for r in pbk.get("risks", []):
            out.append(f"     ⚠ {r}")

    if rep.get("ai_plain"):
        out.append("  AI: " + rep["ai_plain"].replace("\n", " "))
    out.append("  VERDICT: " + rep["verdict"].replace("\n", "\n           "))
    return "\n".join(out)
