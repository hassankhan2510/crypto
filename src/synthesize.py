"""Combine everything into a per-coin report + honest plain-English risk verdict.
NO buy/sell signals -- risk regime, context, and what to watch."""
from config import FUNDING_EXTREME, OI_BUILD_PCT

def build_report(coin, spot24, vol, of, wr, deriv, xprice):
    price = spot24["price"]

    # ---- cross-exchange agreement ----
    prices = [p for p in [price, xprice.get("coinbase"), xprice.get("okx")] if p]
    spread_bp = (max(prices) - min(prices)) / price * 1e4 if len(prices) > 1 else 0.0

    # ---- derivatives flags ----
    fr = deriv.get("funding"); oi = deriv.get("oi_chg"); ls = deriv.get("long_short")
    fund_flag = ""
    if fr is not None:
        fund_flag = "🔴 crowded longs (pay to hold)" if fr > FUNDING_EXTREME else \
                    "🟢 crowded shorts (paid to hold)" if fr < -FUNDING_EXTREME else "neutral"
    oi_flag = ""
    if oi is not None:
        oi_flag = "building" if oi > OI_BUILD_PCT else "unwinding" if oi < -OI_BUILD_PCT else "flat"

    # ---- honest verdict ----
    reg = vol["regime"] if vol else "?"
    exp = vol["expansion"] if vol else "?"
    lines = []
    stand_aside = False

    if vol:
        if reg == "STORM":
            lines.append(f"⚡ **High-risk regime.** Expect ~±{vol['move_pct']:.1f}% over 24h. Size DOWN; wide stops or stay out.")
        elif reg == "CALM" and exp == "CONTRACTING":
            lines.append(f"😴 **Dead/compressed.** Expected move only ~±{vol['move_pct']:.1f}%. Costs eat you here — **stand aside** or wait for expansion.")
            stand_aside = True
        else:
            lines.append(f"🟡 **Normal regime.** Expected ~±{vol['move_pct']:.1f}% over 24h.")
        if exp == "EXPANDING":
            lines.append("🌪️ **Volatility is expanding — a move is opening (direction unknown).** This is the window that matters.")

    # positioning squeeze risk (both-directional, honest)
    if fr is not None and oi is not None and abs(fr) > FUNDING_EXTREME and oi > OI_BUILD_PCT:
        side = "longs" if fr > 0 else "shorts"
        lines.append(f"🎯 Crowded {side} + rising OI → **squeeze risk** (violent move if it unwinds).")

    # flow context (never a signal)
    if of:
        lines.append(f"Flow: aggressors net **{of['cvd_24h']}** (24h), **{of['cvd_4h']}** (4h). "
                     f"Whales **{wr['whale']}**, retail **{wr['retail']}**.")

    verdict = "\n".join(lines) if lines else "No strong read."

    return {
        "coin": coin, "price": price, "chg_pct": spot24["chg_pct"],
        "vol": vol, "of": of, "wr": wr,
        "funding": fr, "fund_flag": fund_flag, "oi_chg": oi, "oi_flag": oi_flag,
        "long_short": ls, "xspread_bp": spread_bp, "n_exch": len(prices),
        "verdict": verdict, "stand_aside": stand_aside,
    }

def console(rep):
    v = rep["vol"]; lines = []
    lines.append(f"\n=== {rep['coin']}  ${rep['price']:,.2f}  ({rep['chg_pct']:+.2f}% 24h)  [{rep['n_exch']} exch, spread {rep['xspread_bp']:.1f}bp] ===")
    if v:
        lines.append(f"  VOL: next-24h ±{v['move_pct']:.1f}% (range {v['range_lo']:,.0f}-{v['range_hi']:,.0f}) | "
                     f"regime {v['regime']} ({v['regime_pctile']:.0f}%ile) | {v['expansion']} | conf {v['confidence']}")
    if rep['funding'] is not None:
        lines.append(f"  DERIV: funding {rep['funding']*100:+.3f}% {rep['fund_flag']} | OI 24h {rep['oi_chg'] if rep['oi_chg'] is None else f'{rep['oi_chg']:+.1f}%'} {rep['oi_flag']} | L/S {rep['long_short']}")
    lines.append("  VERDICT: " + rep["verdict"].replace("\n", "\n           ").replace("**",""))
    return "\n".join(lines)
