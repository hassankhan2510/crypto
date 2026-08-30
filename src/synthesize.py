"""Combine everything into a per-coin report that speaks BOTH languages:
  🟢 IN PLAIN WORDS  — a normal person understands what's happening & what it means
  📊 FOR THE TRADER  — the metrics a 10-yr trader wants (levels, CVD, VPIN, liq, funding)
Plus an honest risk VERDICT. Never buy/sell direction.
Also builds a PORTFOLIO summary for non-trading allocators."""
from config import FUNDING_EXTREME, OI_BUILD_PCT

# ---------------------------------------------------------------- per coin
def build_report(coin, spot24, vol, of, agg, vp, wr, deriv, xprice, mvol, levels, vpin_v):
    price = spot24["price"]
    prices = [p for p in [price, xprice.get("coinbase"), xprice.get("okx")] if p]
    spread_bp = (max(prices) - min(prices)) / price * 1e4 if len(prices) > 1 else 0.0
    fr, oi, ls = deriv.get("funding"), deriv.get("oi_chg"), deriv.get("long_short")
    top_ls, taker_ls, liq = deriv.get("top_ls"), deriv.get("taker_ls"), deriv.get("liq")

    fund_flag = ""
    if fr is not None:
        fund_flag = "crowded longs" if fr > FUNDING_EXTREME else \
                    "crowded shorts" if fr < -FUNDING_EXTREME else "neutral"
    oi_flag = "" if oi is None else ("building" if oi > OI_BUILD_PCT else "unwinding" if oi < -OI_BUILD_PCT else "flat")

    # ---------- PLAIN WORDS (beginner) ----------
    plain = _plain(coin, spot24, vol, agg, wr, fr, oi, liq)

    # ---------- VERDICT (risk, honest) ----------
    verdict, stand_aside = _verdict(vol, of, wr, fr, oi)

    return {
        "coin": coin, "price": price, "chg_pct": spot24["chg_pct"],
        "vol": vol, "of": of, "agg": agg, "vp": vp, "wr": wr, "vpin": vpin_v,
        "funding": fr, "fund_flag": fund_flag, "oi_chg": oi, "oi_flag": oi_flag,
        "long_short": ls, "top_ls": top_ls, "taker_ls": taker_ls, "liq": liq,
        "xspread_bp": spread_bp, "n_exch": len(prices),
        "mvol": mvol, "levels": levels,
        "plain": plain, "verdict": verdict, "stand_aside": stand_aside,
    }

def _human_usd(x):
    ax = abs(x)
    if ax >= 1e9: return f"${x/1e9:.1f}B"
    if ax >= 1e6: return f"${x/1e6:.0f}M"
    if ax >= 1e3: return f"${x/1e3:.0f}K"
    return f"${x:.0f}"

def _plain(coin, spot24, vol, agg, wr, fr, oi, liq=None):
    chg = spot24["chg_pct"]
    move = f"{coin} is {'up' if chg>=0 else 'down'} {abs(chg):.1f}% today."
    if not vol:
        return move
    reg = vol["regime"]
    if reg == "STORM":
        calm = "It's a **wild/high-risk** day — big swings likely."
    elif reg == "CALM":
        calm = "It's **quiet** right now — small moves, not much happening."
    else:
        calm = "It's a **normal** day for movement."
    swing = f"Expect roughly a **±{vol['move_pct']:.1f}%** swing over the next 24h."
    # who's in control, in plain terms
    who = ""
    if agg and agg["venues"]:
        a = agg["agg_pct"]
        who = ("Buyers are pushing harder than sellers right now." if a > 3
               else "Sellers are pushing harder than buyers right now." if a < -3
               else "Buyers and sellers are fairly balanced.")
    big = ""
    if wr and wr["whale"] in ("buying", "selling"):
        big = f" Big players are net **{wr['whale']}**."
    # what it means for a normal holder
    if reg == "STORM":
        mean = "👉 If you just hold, expect a bumpy ride; don't panic on a spike, and avoid big new bets into the chaos."
    elif reg == "CALM" and vol["expansion"] == "CONTRACTING":
        mean = "👉 Not much to do here — calm before a possible move. Patience beats forcing a trade."
    else:
        mean = "👉 Normal conditions. Nothing urgent for a long-term holder."
    liq_note = ""
    if liq and (liq.get("long_liq_usd", 0) + liq.get("short_liq_usd", 0)) > 0:
        ll, sl = liq["long_liq_usd"], liq["short_liq_usd"]
        if ll > sl * 1.3:
            liq_note = f" ({_human_usd(ll)} of bullish bets got force-sold in 24h.)"
        elif sl > ll * 1.3:
            liq_note = f" ({_human_usd(sl)} of bearish bets got squeezed out in 24h.)"
    return f"{move} {calm} {swing} {who}{big}{liq_note}\n{mean}"

def _verdict(vol, of, wr, fr, oi):
    lines, stand_aside = [], False
    if vol:
        reg, exp = vol["regime"], vol["expansion"]
        if reg == "STORM":
            lines.append(f"⚡ High-risk regime (~±{vol['move_pct']:.1f}%/24h). Size DOWN, wider stops, or stay out.")
        elif reg == "CALM" and exp == "CONTRACTING":
            lines.append(f"😴 Compressed/dead (~±{vol['move_pct']:.1f}%). Costs eat you — stand aside / await expansion.")
            stand_aside = True
        else:
            lines.append(f"🟡 Normal regime (~±{vol['move_pct']:.1f}%/24h).")
        if exp == "EXPANDING":
            lines.append("🌪️ Volatility EXPANDING — a move is opening (direction unknown). The window that matters.")
    if fr is not None and oi is not None and abs(fr) > FUNDING_EXTREME and oi > OI_BUILD_PCT:
        side = "longs" if fr > 0 else "shorts"
        lines.append(f"🎯 Crowded {side} + rising OI → squeeze risk (violent unwind possible).")
    return ("\n".join(lines) if lines else "No strong read."), stand_aside

# ---------------------------------------------------------------- portfolio (allocator)
def portfolio_summary(reports):
    vols = [r for r in reports if r["vol"]]
    if not vols: return None
    storms = sum(1 for r in vols if r["vol"]["regime"] == "STORM")
    calms = sum(1 for r in vols if r["vol"]["regime"] == "CALM")
    expanding = sum(1 for r in vols if r["vol"]["expansion"] == "EXPANDING")
    n = len(vols)
    if storms >= n / 2:
        risk = "RISK-OFF"; note = "Most coins are in a high-vol storm. For a portfolio: reduce size / raise cash, expect big swings both ways."
    elif calms >= n / 2 and expanding == 0:
        risk = "QUIET"; note = "Market is calm and compressed. Low opportunity now; a move usually follows quiet — be ready, don't force."
    else:
        risk = "MIXED"; note = "Normal-to-elevated risk. Be selective; favour the coins that are expanding, keep risk controlled."
    avg_move = sum(r["vol"]["move_pct"] for r in vols) / n
    return {"risk": risk, "note": note, "storms": storms, "n": n,
            "expanding": expanding, "avg_move": avg_move}

# ---------------------------------------------------------------- console
def console(rep):
    v = rep["vol"]; L = rep.get("levels") or {}; vp = rep.get("vp") or {}
    out = [f"\n=== {rep['coin']}  ${rep['price']:,.2f}  ({rep['chg_pct']:+.2f}% 24h)  [{rep['n_exch']} exch, spread {rep['xspread_bp']:.1f}bp] ==="]
    out.append("  PLAIN: " + rep["plain"].replace("**", "").replace("\n", "\n         "))
    if v:
        sh = ""
        if v.get("m30_pct") is not None: sh += f" | 30m ±{v['m30_pct']:.1f}%"
        if v.get("h1_pct") is not None: sh += f" | 1h ±{v['h1_pct']:.1f}%"
        out.append(f"  VOL: 24h ±{v['move_pct']:.1f}% (range {v['range_lo']:,.0f}-{v['range_hi']:,.0f}){sh} | {v['regime']} {v['regime_pctile']:.0f}%ile | {v['expansion']} | conf {v['confidence']}")
    ag = rep.get("agg") or {}
    vpin_s = f"{rep['vpin']:.2f}" if rep.get("vpin") is not None else "n/a"
    div_s = ", DIVERGENT" if ag.get("divergence") else ""
    out.append(f"  FLOW: xexch CVD {ag.get('agg_pct',0):+.1f}% ({ag.get('venues',0)} venues{div_s}) | VPIN {vpin_s} | whales {rep['wr']['whale']}")
    if rep["funding"] is not None:
        oi = 'n/a' if rep['oi_chg'] is None else f"{rep['oi_chg']:+.1f}%"
        top = rep.get('top_ls'); tak = rep.get('taker_ls')
        extra = (f" | topL/S {top:.2f}" if top else "") + (f" | takerB/S {tak:.2f}" if tak else "")
        out.append(f"  DERIV: funding {rep['funding']*100:+.3f}% ({rep['fund_flag']}) | OI {oi} {rep['oi_flag']} | L/S {rep['long_short']}{extra}")
    if rep.get("liq"):
        out.append(f"  LIQ(24h): longs {_human_usd(rep['liq']['long_liq_usd'])} / shorts {_human_usd(rep['liq']['short_liq_usd'])}")
    if vp.get("poc"):
        out.append(f"  LEVELS: POC {vp['poc']:,.0f} | sup {vp.get('support')} | res {vp.get('resistance')} | liq↓ {L.get('long_liq',[None])[0]} liq↑ {L.get('short_liq',[None])[0]}")
    pbk = rep.get("playbook")
    if pbk:
        out.append("  PLAYBOOK: " + pbk["headline"])
        for s in pbk["scenarios"]:
            rr = f" (R:R {s['rr']})" if s.get("rr") else ""
            out.append(f"     • if {s['trigger']} → {s['target']}{rr}  [{s['note']}]")
    if rep.get("ai_plain"):
        out.append("  AI: " + rep["ai_plain"].replace("\n", " "))
    out.append("  VERDICT: " + rep["verdict"].replace("\n", "\n           "))
    return "\n".join(out)
