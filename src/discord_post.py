"""Post rich embeds to Discord. Two-language layout per coin (plain + pro),
a market overview and the track-record footer. No webhook -> no-op.

The layout now leads with the COST GATE and the intraday horizon, because those
are the two things that decide whether a day trader should be at the screen at
all. The old "Scenario Playbook" field (long-watch / short-watch / target / R:R)
is gone -- it was a direction signal built on fabricated levels.
"""
import time, requests
from config import DISCORD_WEBHOOK_URL, BRAND, DISCLAIMER, TIER, FACTOR_COIN

COLOR = {"STORM": 0xE03131, "NORMAL": 0xF08C00, "CALM": 0x1971C2}
PRISK = {"RISK-OFF": 0xE03131, "MIXED": 0xF08C00, "QUIET": 0x1971C2, "DEAD": 0x495057}
GATE_ICON = {"OK": "🟢", "THIN": "🟠", "DEAD": "🔴"}


def _px(x):
    """Price formatting that survives sub-dollar coins."""
    if x is None:
        return "n/a"
    ax = abs(float(x))
    d = 0 if ax >= 1000 else 2 if ax >= 10 else 4 if ax >= 0.1 else 6
    return f"{float(x):,.{d}f}"


def _horizon_field(v):
    rows = []
    for c in v.get("cost_table", []):
        rows.append(f"{GATE_ICON.get(c['state'], '·')} `{c['label']:>3}` ±{c['move_pct']:.2f}%"
                    f"  ·  **{c['ratio']:.1f}x** cost")
    it = v.get("intraday_tradeable")
    rows.append("")
    rows.append(f"**Day trading:** {'shortest viable ' + it if it else 'NOT viable right now'}")
    return {"name": "⏱️ Horizons vs cost", "value": "\n".join(rows)[:1024], "inline": False}


def _embed(rep):
    v = rep["vol"] or {}
    reg = v.get("regime", "NORMAL")
    plain = rep.get("ai_plain") or rep["plain"]
    fields = [{"name": "🟢 In plain words", "value": plain[:1000], "inline": False}]

    if TIER in ("retail", "pro") and v:
        fields.append(_horizon_field(v))
        r2 = v.get("fit_r2")
        r2s = "n/a" if r2 is None else f"{r2:+.3f}"
        fields.append({"name": "📈 Model", "value":
            f"Headline **{v.get('headline_label')}** ±{v.get('move_pct', 0):.2f}%\n"
            f"Range `{_px(v.get('range_lo'))}–{_px(v.get('range_hi'))}`\n"
            f"**{reg}** ({v.get('regime_pctile', 0):.0f}%ile"
            f"{'' if v.get('regime_anchored') else ', not cost-anchored'}) · {v.get('expansion')}\n"
            f"walk-forward OOS R² **{r2s}** ({v.get('confidence')})", "inline": True})

        if v.get("season_now") is not None:
            fields.append({"name": "🕐 The clock", "value":
                f"This hour **{v['season_now']:.2f}x** average variance\n"
                f"Busiest **{v.get('season_peak_h'):02d}:00** UTC · deadest **{v.get('season_trough_h'):02d}:00** UTC\n"
                f"({v.get('season_ratio', 0):.2f}x spread in typical move size)", "inline": True})

    if TIER in ("retail", "pro") and rep["funding"] is not None:
        oi = "n/a" if rep["oi_chg"] is None else f"{rep['oi_chg']:+.1f}%"
        val = (f"Funding **{rep['funding']*100:+.3f}%** ({rep['fund_flag']})\n"
               f"OI **{oi}** {rep['oi_flag']}\nCrowd L/S **{rep['long_short']}**")
        if rep.get("top_ls"): val += f"\nTop traders L/S **{rep['top_ls']:.2f}**"
        if rep.get("taker_ls"): val += f"\nFut taker B/S **{rep['taker_ls']:.2f}**"
        fields.append({"name": "🔧 Derivatives", "value": val, "inline": True})

    if TIER == "pro":
        of = rep.get("of") or {}
        bits = []
        for lab in ("1h", "4h", "24h"):
            if of.get(f"cvd_{lab}_pct") is not None:
                p = of.get(f"cvd_{lab}_pctile")
                bits.append(f"`{lab}` **{of[f'cvd_{lab}_pct']:+.1f}%**"
                            + (f" ({p:.0f}th pctile)" if p is not None else ""))
        if bits:
            fields.append({"name": f"🌊 Aggressor flow ({of.get('source')}, {of.get('history_days')}d history)",
                           "value": "\n".join(bits), "inline": False})

        vp_ = rep.get("vpin")
        ag = rep.get("agg") or {}
        misc = []
        if vp_:
            misc.append(f"VPIN **{vp_['vpin']:.3f}**"
                        + (f" ({vp_['pctile']:.0f}th pctile)" if vp_.get("pctile") is not None else ""))
        if ag.get("venues"):
            misc.append(f"Tape **{ag['agg_pct']:+.1f}%** over a common {ag['window_s']:.0f}s window "
                        f"({ag['venues']} venues) — _snapshot, not positioning_")
        if misc:
            fields.append({"name": "🔬 Microstructure", "value": "\n".join(misc), "inline": False})

        fac = rep.get("factor")
        if fac and not fac.get("is_factor"):
            tag = "  ⚡ **coin-specific move**" if fac.get("coin_specific") else ""
            fields.append({"name": f"🔁 vs {FACTOR_COIN}", "value":
                f"beta **{fac['beta']:.2f}** · R² **{fac['r2_vs_factor']:.2f}** · "
                f"own vol **{fac['idio_share']*100:.0f}%**{tag}", "inline": False})

        vp = rep.get("vp") or {}
        if vp.get("poc"):
            fields.append({"name": "🎯 Volume profile (1w)", "value":
                f"POC `{_px(vp['poc'])}` · value area `{_px(vp.get('val'))}–{_px(vp.get('vah'))}`\n"
                f"_{vp.get('note')}_", "inline": False})

    pbk = rep.get("playbook")
    if pbk:
        body = [pbk["headline"]]
        if pbk.get("timing"): body.append("**When:** " + "; ".join(pbk["timing"]))
        if pbk.get("context"): body.append("**Context:** " + ", ".join(pbk["context"]))
        for r in pbk.get("risks", []): body.append(f"⚠ {r}")
        fields.append({"name": "🗺️ Risk map", "value": "\n".join(body)[:1024], "inline": False})

    fields.append({"name": "🧭 Verdict (risk, not a signal)", "value": rep["verdict"][:1000], "inline": False})
    return {"title": f"{rep['coin']}  ·  ${rep['price']:,.2f}  ({rep['chg_pct']:+.2f}% 24h)",
            "color": COLOR.get(reg, 0x868E96), "fields": fields}


def _portfolio_embed(p):
    extra = (f"\n\n**Intraday viable:** {', '.join(p['intraday'])}" if p.get("intraday")
             else "\n\n**Intraday viable:** nothing — day trading is off today")
    return {"title": f"🌍 Market Overview — {p['risk']}",
            "description": (f"{p['note']}{extra}")[:4000],
            "color": PRISK.get(p["risk"], 0x868E96)}


def post(reports, portfolio=None, track=None):
    if not DISCORD_WEBHOOK_URL:
        print("  [discord] no webhook set — skipping post."); return False
    ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    head = f"**{BRAND}** — {ts}\n_{DISCLAIMER}_"
    if track:
        head += f"\n{track}"
    ok = _send({"content": head})
    if portfolio:
        _send({"embeds": [_portfolio_embed(portfolio)]}); time.sleep(0.4)
    for i in range(0, len(reports), 10):
        ok = _send({"embeds": [_embed(r) for r in reports[i:i+10]]}) and ok
        time.sleep(0.5)
    return ok


def _send(payload):
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        if r.status_code in (200, 204):
            return True
        print(f"  [discord] HTTP {r.status_code}: {r.text[:150]}"); return False
    except Exception as e:
        print(f"  [discord] error: {e}"); return False
