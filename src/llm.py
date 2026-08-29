"""Optional AI easy-language layer via OpenRouter (use a FREE model).
Constrained to EXPLAIN the data we give it in simple words — never predict
direction, never say buy/sell, never invent numbers. Falls back to None (the
template plain-words is used) if no key or the call fails."""
import requests
from config import OPENROUTER_API_KEY, OPENROUTER_MODEL

SYSTEM = (
    "You explain crypto market data to a complete beginner. Rewrite the facts you are "
    "given into 2-3 short, calm, simple sentences anyone understands. Rules: ONLY use the "
    "numbers/facts provided; NEVER predict direction; NEVER say buy, sell, long, or short; "
    "NEVER invent data. End with one plain sentence on what it means for a normal holder."
)

def easy_language(facts):
    if not OPENROUTER_API_KEY:
        return None
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}",
                     "Content-Type": "application/json",
                     "X-Title": "Crypto Vol & Risk Intel"},
            json={"model": OPENROUTER_MODEL,
                  "messages": [{"role": "system", "content": SYSTEM},
                               {"role": "user", "content": facts}],
                  "max_tokens": 220, "temperature": 0.3},
            timeout=30)
        j = r.json()
        return j["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  [llm] skipped: {str(e)[:80]}")
        return None

def facts_string(rep):
    """Compact factual summary fed to the model (no opinions)."""
    v = rep["vol"] or {}
    parts = [f"Coin {rep['coin']}, price ${rep['price']:,.0f}, 24h change {rep['chg_pct']:+.1f}%."]
    if v:
        parts.append(f"Volatility regime {v['regime']}, expected 24h move about {v['move_pct']:.1f}%, vol {v['expansion'].lower()}.")
    ag = rep.get("agg") or {}
    if ag.get("venues"):
        parts.append(f"Order flow: aggressors net {'buyers' if ag['agg_pct']>3 else 'sellers' if ag['agg_pct']<-3 else 'balanced'}.")
    if rep.get("wr", {}).get("whale") in ("buying", "selling"):
        parts.append(f"Large players net {rep['wr']['whale']}.")
    if rep.get("top_ls"):
        parts.append(f"Top traders long/short ratio {rep['top_ls']:.2f}.")
    if rep.get("funding") is not None:
        parts.append(f"Funding {rep['funding']*100:+.3f}% ({rep.get('fund_flag','')}).")
    if rep.get("liq"):
        parts.append(f"24h liquidations: longs ${rep['liq']['long_liq_usd']:,.0f}, shorts ${rep['liq']['short_liq_usd']:,.0f}.")
    return " ".join(parts)
