"""Optional Coinglass integration — REAL aggregated liquidations across 30+ exchanges.
Gated on COINGLASS_API_KEY (free tier). Without a key this returns None and the
product falls back to estimated liquidation levels. Endpoints follow Coinglass v4;
parsing is defensive (field names vary by plan) and never raises."""
import requests
from config import COINGLASS_API_KEY

BASE = "https://open-api-v4.coinglass.com"

def _get(path, params):
    r = requests.get(BASE + path, params=params,
                     headers={"CG-API-KEY": COINGLASS_API_KEY, "accept": "application/json"},
                     timeout=10)
    j = r.json()
    if str(j.get("code")) not in ("0", "200", "success", "None"):
        return None
    return j.get("data")

def _num(d, *keys):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            try: return float(d[k])
            except Exception: pass
    return 0.0

def liquidations(coin):
    """24h aggregated long/short liquidation $ for the coin. None if no key/unavailable."""
    if not COINGLASS_API_KEY:
        return None
    try:
        data = _get("/api/futures/liquidation/history",
                    {"symbol": f"{coin}USDT", "interval": "1h", "limit": 24})
        if not data:
            return None
        rows = data if isinstance(data, list) else data.get("list", [])
        longl = sum(_num(d, "longLiquidationUsd", "long_liquidation_usd", "longLiquidation") for d in rows)
        shortl = sum(_num(d, "shortLiquidationUsd", "short_liquidation_usd", "shortLiquidation") for d in rows)
        if longl == 0 and shortl == 0:
            return None
        return {"long_liq_usd": longl, "short_liq_usd": shortl}
    except Exception:
        return None
