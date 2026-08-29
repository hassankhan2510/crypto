"""Multi-exchange free data: spot OHLCV + taker flow (Binance), cross-exchange
price confirmation (Coinbase, OKX), and Binance-futures derivatives context
(funding, open interest, long/short) -- all free, no API key."""
import numpy as np, pandas as pd
from src.http import get_json

BINANCE = "https://api.binance.com"
BINANCE_F = "https://fapi.binance.com"
COINBASE = "https://api.exchange.coinbase.com"
OKX = "https://www.okx.com"

# ---------- Binance spot ----------
def binance_klines(coin, interval="1h", limit=1000):
    """Hourly OHLCV with taker-buy volume (real aggressor flow)."""
    j = get_json(f"{BINANCE}/api/v3/klines",
                 {"symbol": f"{coin}USDT", "interval": interval, "limit": limit})
    df = pd.DataFrame(j, columns=["t","o","h","l","c","v","ct","qv","n","tbb","tbq","x"])
    df["time"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    for k in ["o","h","l","c","v","qv","tbb","tbq","n"]:
        df[k] = df[k].astype(float)
    df["taker_sell_q"] = df["qv"] - df["tbq"]
    df["cvd_step"] = df["tbq"] - df["taker_sell_q"]      # signed aggressive $ per bar
    return df.set_index("time")

def binance_24h(coin):
    j = get_json(f"{BINANCE}/api/v3/ticker/24hr", {"symbol": f"{coin}USDT"})
    return {"price": float(j["lastPrice"]), "chg_pct": float(j["priceChangePercent"]),
            "quote_vol": float(j["quoteVolume"])}

def binance_aggtrades(coin, limit=1000):
    """Recent trades for whale-vs-retail split."""
    j = get_json(f"{BINANCE}/api/v3/aggTrades", {"symbol": f"{coin}USDT", "limit": limit})
    df = pd.DataFrame(j)
    if df.empty: return df
    df["p"] = df["p"].astype(float); df["q"] = df["q"].astype(float)
    df["usd"] = df["p"] * df["q"]
    df["buy"] = ~df["m"]                                   # m=True => buyer is maker => SELL aggressor
    return df

# ---------- cross-exchange price ----------
def coinbase_price(coin):
    try:
        j = get_json(f"{COINBASE}/products/{coin}-USD/ticker")
        return float(j["price"])
    except Exception:
        return None

def okx_price(coin):
    try:
        j = get_json(f"{OKX}/api/v5/market/ticker", {"instId": f"{coin}-USDT"})
        return float(j["data"][0]["last"])
    except Exception:
        return None

# ---------- Binance futures derivatives ----------
def funding_rate(coin):
    try:
        j = get_json(f"{BINANCE_F}/fapi/v1/premiumIndex", {"symbol": f"{coin}USDT"})
        return float(j["lastFundingRate"])
    except Exception:
        return None

def open_interest_change(coin):
    """24h OI % change from hourly OI history."""
    try:
        j = get_json(f"{BINANCE_F}/futures/data/openInterestHist",
                     {"symbol": f"{coin}USDT", "period": "1h", "limit": 25})
        v = [float(x["sumOpenInterest"]) for x in j]
        if len(v) < 2 or v[0] == 0: return None
        return (v[-1] - v[0]) / v[0] * 100
    except Exception:
        return None

def long_short_ratio(coin):
    try:
        j = get_json(f"{BINANCE_F}/futures/data/globalLongShortAccountRatio",
                     {"symbol": f"{coin}USDT", "period": "1h", "limit": 1})
        return float(j[-1]["longShortRatio"])
    except Exception:
        return None
