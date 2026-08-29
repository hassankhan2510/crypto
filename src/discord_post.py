"""Post rich embeds to a Discord webhook. No webhook set -> no-op (safe)."""
import time, requests
from config import DISCORD_WEBHOOK_URL, BRAND, DISCLAIMER

COLOR = {"STORM": 0xE03131, "NORMAL": 0xF08C00, "CALM": 0x1971C2}

def _embed(rep):
    v = rep["vol"]; reg = v["regime"] if v else "NORMAL"
    fields = []
    if v:
        fields.append({"name": "📈 Volatility (24h forecast)",
                       "value": f"Expected **±{v['move_pct']:.1f}%**\nRange `{v['range_lo']:,.0f} – {v['range_hi']:,.0f}`\nRegime **{reg}** ({v['regime_pctile']:.0f}%ile) · {v['expansion']}\nConfidence: {v['confidence']}",
                       "inline": True})
    if rep["funding"] is not None:
        oi = "n/a" if rep["oi_chg"] is None else f"{rep['oi_chg']:+.1f}%"
        fields.append({"name": "🔧 Derivatives",
                       "value": f"Funding **{rep['funding']*100:+.3f}%** {rep['fund_flag']}\nOI 24h **{oi}** {rep['oi_flag']}\nLong/Short **{rep['long_short']}**",
                       "inline": True})
    if rep["of"]:
        of, wr = rep["of"], rep["wr"]
        fields.append({"name": "🌊 Order flow",
                       "value": f"Aggressors: **{of['cvd_24h']}** 24h / **{of['cvd_4h']}** 4h\nWhales **{wr['whale']}** · Retail **{wr['retail']}**",
                       "inline": False})
    fields.append({"name": "🧭 Verdict", "value": rep["verdict"][:1000], "inline": False})
    return {"title": f"{rep['coin']}  ·  ${rep['price']:,.2f}  ({rep['chg_pct']:+.2f}% 24h)",
            "color": COLOR.get(reg, 0x868E96), "fields": fields}

def post(reports):
    if not DISCORD_WEBHOOK_URL:
        print("  [discord] no webhook set — skipping post.")
        return False
    ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    ok = True
    # header
    _send({"content": f"**{BRAND}** — {ts}\n_{DISCLAIMER}_"})
    for i in range(0, len(reports), 10):        # Discord max 10 embeds/msg
        batch = [_embed(r) for r in reports[i:i+10]]
        ok = _send({"embeds": batch}) and ok
        time.sleep(0.5)
    return ok

def _send(payload):
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        if r.status_code in (200, 204): return True
        print(f"  [discord] HTTP {r.status_code}: {r.text[:150]}"); return False
    except Exception as e:
        print(f"  [discord] error: {e}"); return False
