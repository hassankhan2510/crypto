"""Generate the free GitHub Pages dashboard (docs/).
 - docs/data.json : the latest analysis (regenerated every run)
 - docs/index.html: static page that fetches data.json, auto-refreshes every 60s,
   AND opens Binance WebSockets client-side so the PRICE ticks in real time.
Enable: repo Settings -> Pages -> Source = main /docs."""
import os, json, time

DOCS = os.path.join(os.path.dirname(__file__), "..", "docs")

def _f(x):
    try: return round(float(x), 6)
    except Exception: return None

def _coin_json(r):
    v = r.get("vol") or {}; ag = r.get("agg") or {}; pb = r.get("playbook") or {}
    of = r.get("of") or {}; fac = r.get("factor") or {}; vpn = r.get("vpin") or {}
    return {
        "coin": r["coin"], "price": _f(r["price"]), "chg": _f(r["chg_pct"]),
        "plain": (r.get("ai_plain") or r.get("plain", "")).replace("**", ""),
        "vol": {"move": _f(v.get("move_pct")), "lo": _f(v.get("range_lo")), "hi": _f(v.get("range_hi")),
                "horizon": v.get("headline_label"), "intraday": v.get("intraday_tradeable"),
                "regime": v.get("regime"), "pctile": _f(v.get("regime_pctile")),
                "anchored": bool(v.get("regime_anchored")),
                "expansion": v.get("expansion"), "conf": v.get("confidence"),
                "r2": _f(v.get("fit_r2")), "r2_kind": v.get("r2_kind"),
                "season_now": _f(v.get("season_now")),
                "season_peak_h": v.get("season_peak_h"), "season_trough_h": v.get("season_trough_h"),
                "season_ratio": _f(v.get("season_ratio")),
                "costs": [{"label": c["label"], "move": _f(c["move_pct"]),
                           "ratio": _f(c["ratio"]), "state": c["state"]}
                          for c in v.get("cost_table", [])]} if v else None,
        "flow": {lab: {"pct": _f(of.get(f"cvd_{lab}_pct")), "pctile": _f(of.get(f"cvd_{lab}_pctile"))}
                 for lab in ("1h", "4h", "24h") if of.get(f"cvd_{lab}_pct") is not None},
        "flow_meta": {"source": of.get("source"), "days": _f(of.get("history_days"))},
        "tape": {"pct": _f(ag.get("agg_pct")), "window_s": _f(ag.get("window_s")),
                 "venues": ag.get("venues"), "divergent": ag.get("divergence")},
        "vpin": {"v": _f(vpn.get("vpin")), "pctile": _f(vpn.get("pctile"))} if vpn else None,
        "factor": ({"beta": _f(fac.get("beta")), "r2": _f(fac.get("r2_vs_factor")),
                    "idio": _f(fac.get("idio_share")), "specific": bool(fac.get("coin_specific"))}
                   if fac and not fac.get("is_factor") else None),
        "deriv": {"funding": _f(r.get("funding")), "fund_flag": r.get("fund_flag"),
                  "oi": _f(r.get("oi_chg")), "top_ls": _f(r.get("top_ls")),
                  "taker_ls": _f(r.get("taker_ls"))},
        "liq": ({"long": _f(r["liq"]["long_liq_usd"]), "short": _f(r["liq"]["short_liq_usd"])}
                if r.get("liq") else None),
        "vp": r.get("vp"),
        "playbook": {"headline": pb.get("headline"), "context": pb.get("context", []),
                     "timing": pb.get("timing", []), "risks": pb.get("risks", []),
                     "cost_state": pb.get("cost_state")} if pb else None,
        "verdict": r.get("verdict", "").replace("**", ""),
    }


def write(reports, portfolio=None, track_line=None):
    os.makedirs(DOCS, exist_ok=True)
    data = {"updated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
            "market": portfolio, "track": track_line,
            "coins": [_coin_json(r) for r in reports]}
    with open(os.path.join(DOCS, "data.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as f:
        f.write(_HTML)
    print(f"  [dashboard] wrote docs/data.json ({len(reports)} coins) + index.html")

_HTML = r"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Crypto Vol &amp; Risk Intel</title>
<style>
:root{--bg:#0b0e14;--card:#151a23;--mut:#8b95a5;--fg:#e6e9ef;--line:#232a36;
--storm:#e03131;--normal:#f08c00;--calm:#1971c2;--up:#2fb344;--down:#e03131;
--ok:#2fb344;--thin:#f08c00;--dead:#e03131;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1150px;margin:0 auto;padding:20px}
h1{font-size:20px;margin:0 0 2px}.sub{color:var(--mut);font-size:13px;margin-bottom:16px}
.banner{padding:12px 16px;border-radius:10px;margin-bottom:16px;background:#151a23;border:1px solid var(--line)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.top{display:flex;justify-content:space-between;align-items:baseline}
.coin{font-size:18px;font-weight:700}.px{font-variant-numeric:tabular-nums;font-weight:600}
.chg.up{color:var(--up)}.chg.down{color:var(--down)}
.tag{display:inline-block;font-size:11px;padding:2px 8px;border-radius:20px;font-weight:700;margin-left:6px}
.STORM{background:rgba(224,49,49,.18);color:#ff8787}
.NORMAL{background:rgba(240,140,0,.18);color:#ffc078}
.CALM{background:rgba(25,113,194,.18);color:#74c0fc}
.plain{margin:10px 0;color:#d7dce5}.small{color:var(--mut);font-size:12px}
.row{display:flex;flex-wrap:wrap;gap:6px 14px;margin:8px 0;font-size:13px}
.k{color:var(--mut)}
table.hz{width:100%;border-collapse:collapse;margin:10px 0;font-size:13px;
font-variant-numeric:tabular-nums}
table.hz td{padding:3px 6px;border-top:1px solid var(--line)}
table.hz td:first-child{color:var(--mut);width:52px}
.pill{font-size:11px;font-weight:700;padding:1px 7px;border-radius:20px}
.pill.OK{background:rgba(47,179,68,.18);color:#69db7c}
.pill.THIN{background:rgba(240,140,0,.18);color:#ffc078}
.pill.DEAD{background:rgba(224,49,49,.18);color:#ff8787}
.pb{margin-top:10px;border-top:1px solid var(--line);padding-top:10px;font-size:13px}
.verdict{margin-top:8px;font-size:13px;white-space:pre-line;color:#c8cfdb}
.foot{color:var(--mut);font-size:12px;margin-top:20px;text-align:center;line-height:1.7}
</style></head><body><div class="wrap">
<h1>📊 Crypto Vol &amp; Risk Intel</h1>
<div class="sub" id="sub">loading…</div>
<div id="banner"></div><div class="grid" id="grid"></div>
<div class="foot">Analytics, not financial advice. We forecast RISK — volatility, regime and
<b>cost</b> — never direction.<br>Every band is a 1σ forecast from a HAR model scored
<b>walk-forward out-of-sample</b>; the R² shown is that OOS number, not an in-sample fit.<br>
Price is live via Binance WebSocket; analysis refreshes each run.</div>
</div>
<script>
const WS={},PX={};
function fmt(n,d=0){return n==null?"–":Number(n).toLocaleString(undefined,{maximumFractionDigits:d,minimumFractionDigits:d})}
function liveWS(coins){coins.forEach(c=>{const s=c.toLowerCase()+"usdt";
 try{const w=new WebSocket("wss://stream.binance.com:9443/ws/"+s+"@trade");
  w.onmessage=e=>{const p=parseFloat(JSON.parse(e.data).p);PX[c]=p;
   const el=document.getElementById("px-"+c);if(el)el.textContent="$"+fmt(p,p<10?4:2)};
  WS[c]=w;}catch(e){}});}
function hzTable(v){
 if(!v||!v.costs||!v.costs.length)return"";
 const rows=v.costs.map(c=>`<tr><td>${c.label}</td><td>±${fmt(c.move,2)}%</td>
  <td>${fmt(c.ratio,1)}× cost</td><td><span class="pill ${c.state}">${c.state}</span></td></tr>`).join("");
 return`<table class="hz">${rows}</table>`;}
function card(c){
 const v=c.vol||{},pb=c.playbook,dv=c.deriv||{},fa=c.factor,fl=c.flow||{};
 const reg=v.regime||"NORMAL";
 const flowBits=Object.keys(fl).map(k=>`<span><span class="k">${k}</span> ${fmt(fl[k].pct,1)}%${fl[k].pctile!=null?` <span class="small">(${fmt(fl[k].pctile,0)}%ile)</span>`:""}</span>`).join("");
 return `<div class="card"><div class="top">
   <div><span class="coin">${c.coin}</span><span class="tag ${reg}">${reg}</span></div>
   <div><span class="px" id="px-${c.coin}">$${fmt(c.price,2)}</span>
     <span class="chg ${c.chg>=0?"up":"down"}"> ${c.chg>=0?"+":""}${fmt(c.chg,2)}%</span></div></div>
  <div class="plain">${c.plain||""}</div>
  ${hzTable(v)}
  <div class="row"><span><span class="k">Day trading</span> <b>${v.intraday?("viable from "+v.intraday):"not viable now"}</b></span></div>
  <div class="row"><span><span class="k">Headline ${v.horizon||""}</span> ${fmt(v.lo)}–${fmt(v.hi)}</span>
   <span><span class="k">Vol</span> ${v.expansion||"–"}</span>
   <span><span class="k">OOS R²</span> ${v.r2==null?"n/a":(v.r2>=0?"+":"")+fmt(v.r2,3)}</span></div>
  ${v.season_now!=null?`<div class="row"><span><span class="k">Clock</span> this hour ${fmt(v.season_now,2)}× avg variance · busiest ${String(v.season_peak_h).padStart(2,"0")}:00 UTC, deadest ${String(v.season_trough_h).padStart(2,"0")}:00 UTC</span></div>`:""}
  ${flowBits?`<div class="row"><span class="k">Aggressor flow</span>${flowBits}</div>`:""}
  <div class="row"><span><span class="k">Funding</span> ${dv.funding!=null?(dv.funding*100).toFixed(3)+"%":"–"}</span>
   <span><span class="k">Top L/S</span> ${fmt(dv.top_ls,2)}</span>
   ${c.liq?`<span><span class="k">Liq 24h</span> L ${fmt(c.liq.long)} / S ${fmt(c.liq.short)}</span>`:""}</div>
  ${fa?`<div class="row small">β ${fmt(fa.beta,2)} to BTC · R² ${fmt(fa.r2,2)} · ${fmt(fa.idio*100,0)}% its own${fa.specific?" · <b>coin-specific move</b>":""}</div>`:""}
  ${pb?`<div class="pb"><b>${pb.headline||""}</b>
   ${pb.timing&&pb.timing.length?`<div class="small">When: ${pb.timing.join("; ")}</div>`:""}
   ${pb.context&&pb.context.length?`<div class="small">Context: ${pb.context.join(", ")}</div>`:""}
   ${(pb.risks||[]).map(r=>`<div class="small">⚠ ${r}</div>`).join("")}</div>`:""}
  <div class="verdict">${c.verdict||""}</div></div>`;}
async function load(){
 try{const d=await (await fetch("data.json?"+Date.now())).json();
  document.getElementById("sub").textContent="Updated "+d.updated+" · price live";
  const b=document.getElementById("banner");
  if(d.market){b.innerHTML=`🌍 <b>Market: ${d.market.risk}</b> — ${d.market.note}`;}
  if(d.track)b.innerHTML+=`<div class="small" style="margin-top:6px">${d.track.replace(/\*\*/g,"")}</div>`;
  document.getElementById("grid").innerHTML=d.coins.map(card).join("");
  if(!Object.keys(WS).length)liveWS(d.coins.map(c=>c.coin));
 }catch(e){document.getElementById("sub").textContent="failed to load data.json";}}
load();setInterval(load,60000);
</script></body></html>"""
