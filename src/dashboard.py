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
    return {
        "coin": r["coin"], "price": _f(r["price"]), "chg": _f(r["chg_pct"]),
        "plain": (r.get("ai_plain") or r.get("plain", "")).replace("**", ""),
        "vol": {"move": _f(v.get("move_pct")), "lo": _f(v.get("range_lo")), "hi": _f(v.get("range_hi")),
                "m30": _f(v.get("m30_pct")), "h1": _f(v.get("h1_pct")),
                "regime": v.get("regime"), "pctile": _f(v.get("regime_pctile")),
                "expansion": v.get("expansion"), "conf": v.get("confidence")} if v else None,
        "flow": {"cvd": _f(ag.get("agg_pct")), "venues": ag.get("venues"),
                 "divergent": ag.get("divergence"), "vpin": _f(r.get("vpin")),
                 "whale": r.get("wr", {}).get("whale")},
        "deriv": {"funding": _f(r.get("funding")), "fund_flag": r.get("fund_flag"),
                  "oi": _f(r.get("oi_chg")), "top_ls": _f(r.get("top_ls")),
                  "taker_ls": _f(r.get("taker_ls"))},
        "liq": ({"long": _f(r["liq"]["long_liq_usd"]), "short": _f(r["liq"]["short_liq_usd"])}
                if r.get("liq") else None),
        "playbook": {"headline": pb.get("headline"), "context": pb.get("context", []),
                     "support": _f(pb.get("support")), "resistance": _f(pb.get("resistance")),
                     "long_liq": _f(pb.get("long_liq")), "short_liq": _f(pb.get("short_liq")),
                     "scenarios": pb.get("scenarios", [])} if pb else None,
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
<title>Crypto Vol & Risk Intel</title>
<style>
:root{--bg:#0b0e14;--card:#151a23;--mut:#8b95a5;--fg:#e6e9ef;--line:#232a36;
--storm:#e03131;--normal:#f08c00;--calm:#1971c2;--up:#2fb344;--down:#e03131;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:20px}
h1{font-size:20px;margin:0 0 2px}.sub{color:var(--mut);font-size:13px;margin-bottom:16px}
.banner{padding:12px 16px;border-radius:10px;margin-bottom:16px;font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
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
.k{color:var(--mut)}.pb{margin-top:10px;border-top:1px solid var(--line);padding-top:10px;font-size:13px}
.sc{margin:4px 0}.foot{color:var(--mut);font-size:12px;margin-top:20px;text-align:center}
</style></head><body><div class="wrap">
<h1>📊 Crypto Vol &amp; Risk Intel</h1>
<div class="sub" id="sub">loading…</div>
<div id="banner"></div><div class="grid" id="grid"></div>
<div class="foot">Analytics, not financial advice. We forecast RISK (volatility/regime), never direction. Price is live; analysis refreshes each run.</div>
</div>
<script>
const WS={}, PX={};
function fmt(n,d=0){return n==null?"–":Number(n).toLocaleString(undefined,{maximumFractionDigits:d})}
function liveWS(coins){
 coins.forEach(c=>{const s=c.toLowerCase()+"usdt";
  try{const w=new WebSocket("wss://stream.binance.com:9443/ws/"+s+"@trade");
   w.onmessage=e=>{const p=parseFloat(JSON.parse(e.data).p);PX[c]=p;
    const el=document.getElementById("px-"+c);if(el)el.textContent="$"+fmt(p, p<10?4:2)};
   WS[c]=w;}catch(e){}});}
function card(c){
 const v=c.vol||{},pb=c.playbook,fl=c.flow||{},dv=c.deriv||{};
 const reg=v.regime||"NORMAL";
 let sc=(pb&&pb.scenarios||[]).map(s=>`<div class="sc">• <b>${s.trigger}</b> → ${s.target}${s.rr?` (R:R ${s.rr})`:""} <span class="small">${s.note}</span></div>`).join("");
 return `<div class="card"><div class="top">
   <div><span class="coin">${c.coin}</span><span class="tag ${reg}">${reg}</span></div>
   <div><span class="px" id="px-${c.coin}">$${fmt(c.price,2)}</span>
     <span class="chg ${c.chg>=0?"up":"down"}"> ${c.chg>=0?"+":""}${fmt(c.chg,2)}%</span></div></div>
  <div class="plain">${c.plain||""}</div>
  <div class="row"><span><span class="k">Exp move</span> ${v.m30!=null?`30m ±${fmt(v.m30,1)}% · `:""}${v.h1!=null?`1h ±${fmt(v.h1,1)}% · `:""}24h ±${fmt(v.move,1)}%</span></div>
  <div class="row"><span><span class="k">24h range</span> ${fmt(v.lo)}–${fmt(v.hi)}</span>
   <span><span class="k">Vol</span> ${v.expansion||"–"}</span></div>
  <div class="row"><span><span class="k">Flow CVD</span> ${fmt(fl.cvd,1)}%${fl.divergent?" ⚠":""}</span>
   <span><span class="k">VPIN</span> ${fmt(fl.vpin,2)}</span>
   <span><span class="k">Whales</span> ${fl.whale||"–"}</span></div>
  <div class="row"><span><span class="k">Funding</span> ${dv.funding!=null?(dv.funding*100).toFixed(3)+"%":"–"}</span>
   <span><span class="k">Top L/S</span> ${fmt(dv.top_ls,2)}</span>
   ${c.liq?`<span><span class="k">Liq 24h</span> L ${fmt(c.liq.long)} / S ${fmt(c.liq.short)}</span>`:""}</div>
  ${pb?`<div class="pb"><b>${pb.headline||""}</b>
   ${pb.context&&pb.context.length?`<div class="small">Context: ${pb.context.join(", ")}</div>`:""}
   ${pb.support?`<div class="small">Zones: sup ${fmt(pb.support)} · res ${fmt(pb.resistance)}${pb.long_liq?" · liq↓ "+fmt(pb.long_liq):""}${pb.short_liq?" · liq↑ "+fmt(pb.short_liq):""}</div>`:""}
   ${sc}</div>`:""}</div>`;}
async function load(){
 try{const d=await (await fetch("data.json?"+Date.now())).json();
  document.getElementById("sub").textContent="Updated "+d.updated+" · price live";
  const b=document.getElementById("banner");
  if(d.market){const col={"RISK-OFF":"var(--storm)","MIXED":"var(--normal)","QUIET":"var(--calm)"}[d.market.risk]||"var(--card)";
   b.style.background=col.replace("var(--","rgba(").replace(")",",0.18)").includes("rgba")?"#151a23":col;
   b.innerHTML=`🌍 <b>Market: ${d.market.risk}</b> — ${d.market.note}`;b.style.background="#151a23";b.style.border="1px solid var(--line)";}
  if(d.track)b.innerHTML+=`<div class="small" style="margin-top:6px">${d.track.replace(/\*\*/g,"")}</div>`;
  document.getElementById("grid").innerHTML=d.coins.map(card).join("");
  const coins=d.coins.map(c=>c.coin);
  if(!Object.keys(WS).length)liveWS(coins);
 }catch(e){document.getElementById("sub").textContent="failed to load data.json";}}
load();setInterval(load,60000);
</script></body></html>"""
