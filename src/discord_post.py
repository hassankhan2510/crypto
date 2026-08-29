"""Post rich embeds to Discord. Two-language layout per coin (plain + pro),
a portfolio summary, and the track-record footer. No webhook -> no-op."""
import time, requests
from config import DISCORD_WEBHOOK_URL, BRAND, DISCLAIMER, TIER

COLOR = {"STORM": 0xE03131, "NORMAL": 0xF08C00, "CALM": 0x1971C2}
PRISK = {"RISK-OFF": 0xE03131, "MIXED": 0xF08C00, "QUIET": 0x1971C2}

def _fmt_levels(rep):
    vp = rep.get("vp") or {}; L = rep.get("levels") or {}
    bits = []
    if vp.get("poc"): bits.append(f"POC `{vp['poc']:,.0f}`")
    if vp.get("support"): bits.append(f"Sup `{vp['support']:,.0f}`")
    if vp.get("resistance"): bits.append(f"Res `{vp['resistance']:,.0f}`")
    if L.get("long_liq"): bits.append(f"Long-liq↓ `{L['long_liq'][0]:,.0f}`")
    if L.get("short_liq"): bits.append(f"Short-liq↑ `{L['short_liq'][0]:,.0f}`")
    return " · ".join(bits) if bits else "—"

def _embed(rep):
    v = rep["vol"]; reg = v["regime"] if v else "NORMAL"
    fields = [{"name": "🟢 In plain words", "value": rep["plain"][:1000], "inline": False}]

    if TIER in ("retail", "pro"):
        if v:
            fields.append({"name": "📈 Volatility (24h)",
                "value": f"±**{v['move_pct']:.1f}%** · `{v['range_lo']:,.0f}–{v['range_hi']:,.0f}`\n**{reg}** ({v['regime_pctile']:.0f}%ile) · {v['expansion']}\nconf {v['confidence']}", "inline": True})
        if rep["funding"] is not None:
            oi = "n/a" if rep["oi_chg"] is None else f"{rep['oi_chg']:+.1f}%"
            val = f"Funding **{rep['funding']*100:+.3f}%** ({rep['fund_flag']})\nOI **{oi}** {rep['oi_flag']}\nCrowd L/S **{rep['long_short']}**"
            if rep.get("top_ls"): val += f"\nTop traders L/S **{rep['top_ls']:.2f}**"
            if rep.get("taker_ls"): val += f"\nFut taker B/S **{rep['taker_ls']:.2f}**"
            fields.append({"name": "🔧 Derivatives", "value": val, "inline": True})
        if rep.get("liq"):
            from src.synthesize import _human_usd
            fields.append({"name": "💥 Liquidations (24h)",
                "value": f"Longs wiped **{_human_usd(rep['liq']['long_liq_usd'])}**\nShorts wiped **{_human_usd(rep['liq']['short_liq_usd'])}**", "inline": True})

    if TIER == "pro":
        ag = rep.get("agg") or {}
        vpin_s = f"{rep['vpin']:.2f}" if rep.get("vpin") is not None else "n/a"
        div = " ⚠️divergent" if ag.get("divergence") else ""
        fields.append({"name": "🌊 Order flow (cross-exchange)",
            "value": f"Agg CVD **{ag.get('agg_pct',0):+.1f}%** ({ag.get('venues',0)} venues){div}\nVPIN toxicity **{vpin_s}**\nWhales **{rep['wr']['whale']}** · Retail **{rep['wr']['retail']}**", "inline": False})
        fields.append({"name": "🎯 Key levels (est.)", "value": _fmt_levels(rep), "inline": False})

    fields.append({"name": "🧭 Verdict (risk, not a signal)", "value": rep["verdict"][:1000], "inline": False})
    return {"title": f"{rep['coin']}  ·  ${rep['price']:,.2f}  ({rep['chg_pct']:+.2f}% 24h)",
            "color": COLOR.get(reg, 0x868E96), "fields": fields}

def _portfolio_embed(p):
    return {"title": f"🌍 Market Overview — {p['risk']}",
            "description": f"{p['note']}\n\n**{p['storms']}/{p['n']}** coins in storm · **{p['expanding']}** expanding · avg expected move **±{p['avg_move']:.1f}%**",
            "color": PRISK.get(p["risk"], 0x868E96)}

def post(reports, portfolio=None, track=None):
    if not DISCORD_WEBHOOK_URL:
        print("  [discord] no webhook set — skipping post."); return False
    ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    head = f"**{BRAND}** — {ts}\n_{DISCLAIMER}_"
    if track: head += f"\n{track}"
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
        if r.status_code in (200, 204): return True
        print(f"  [discord] HTTP {r.status_code}: {r.text[:150]}"); return False
    except Exception as e:
        print(f"  [discord] error: {e}"); return False
