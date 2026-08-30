"""Multi-exchange free data: spot OHLCV + taker flow (Binance), cross-exchange
price confirmation (Coinbase, OKX), and Binance-futures derivatives context
(funding, open interest, long/short) -- all free, no API key.

HISTORY: Binance caps a single klines call at 1000 bars. The old code took that
cap as the dataset (42 days of hourly bars) and fitted a HAR on it, which is why
the shipped model had a NEGATIVE out-of-sample R2. klines() below paginates with
startTime and caches to disk, so the model sees the ~2 years its paper assumed.
"""
import os, time
import pandas as pd
from src.http import get_json
from config import CACHE_DIR, CACHE_TTL_S

BINANCE = "https://api.binance.com"
BINANCE_F = "https://fapi.binance.com"
COINBASE = "https://api.exchange.coinbase.com"
OKX = "https://www.okx.com"

_INTERVAL_S = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
_COLS = ["t", "o", "h", "l", "c", "v", "ct", "qv", "n", "tbb", "tbq", "x"]
_MEM = {}   # in-process cache: one fetch per (coin, interval) per run


# ---------------------------------------------------------------- disk cache
def _cache_path(coin, interval):
    return os.path.join(CACHE_DIR, f"{coin}_{interval}.pkl")

def _cache_read(coin, interval):
    p = _cache_path(coin, interval)
    if not os.path.exists(p):
        return None
    try:
        return pd.read_pickle(p)
    except Exception:
        return None

def _cache_write(coin, interval, df):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        df.to_pickle(_cache_path(coin, interval))
    except Exception:
        pass        # the cache is a nicety, never required


def _fetch_range(symbol, interval, start_ms, end_ms):
    """Page through klines from start_ms to end_ms. Returns raw rows."""
    out, cur = [], int(start_ms)
    while cur < end_ms:
        j = get_json(f"{BINANCE}/api/v3/klines",
                     {"symbol": symbol, "interval": interval,
                      "startTime": cur, "limit": 1000}, tries=3, timeout=20)
        if not j:
            break
        out += j
        cur = int(j[-1][6]) + 1          # close time of last bar + 1ms
        if len(j) < 1000:
            break
    return out


def _frame(rows):
    df = pd.DataFrame(rows, columns=_COLS)
    if df.empty:
        return df
    df["time"] = pd.to_datetime(df["t"].astype("int64"), unit="ms", utc=True)
    for k in ["o", "h", "l", "c", "v", "qv", "tbb", "tbq", "n"]:
        df[k] = df[k].astype(float)
    df["taker_sell_q"] = df["qv"] - df["tbq"]
    df["cvd_step"] = df["tbq"] - df["taker_sell_q"]      # signed aggressive $ per bar
    df = df.set_index("time").sort_index()
    return df[~df.index.duplicated(keep="last")]


def klines(coin, interval="1h", bars=1000):
    """Up to `bars` bars of history, paginated past Binance's 1000-row cap.

    Uses a disk cache and only fetches the missing tail on later runs, so the
    2-year pull costs ~18 requests once and ~1 request per run afterwards.
    """
    key = (coin, interval)
    if key in _MEM and len(_MEM[key]) >= bars * 0.95:
        return _MEM[key].tail(bars)

    sec = _INTERVAL_S[interval]
    now_ms = int(time.time() * 1000)
    want_start = now_ms - bars * sec * 1000
    symbol = f"{coin}USDT"

    cached = _cache_read(coin, interval)
    if cached is not None and not cached.empty:
        last_ms = int(cached.index[-1].timestamp() * 1000)
        covers = int(cached.index[0].timestamp() * 1000) <= want_start + sec * 1000
        fresh = (now_ms - last_ms) < CACHE_TTL_S * 1000
        if covers and fresh:
            _MEM[key] = cached
            return cached.tail(bars)
        if covers:                                  # only the tail is missing
            rows = _fetch_range(symbol, interval, last_ms + 1, now_ms)
            df = pd.concat([cached, _frame(rows)]) if rows else cached
            df = df[~df.index.duplicated(keep="last")].sort_index()
            _cache_write(coin, interval, df); _MEM[key] = df
            return df.tail(bars)

    df = _frame(_fetch_range(symbol, interval, want_start, now_ms))
    if df.empty:
        raise RuntimeError(f"no klines for {symbol} {interval}")
    if cached is not None and not cached.empty:
        df = pd.concat([cached, df])
        df = df[~df.index.duplicated(keep="last")].sort_index()
    _cache_write(coin, interval, df); _MEM[key] = df
    return df.tail(bars)


def binance_klines(coin, interval="1h", limit=1000):
    """Backwards-compatible shim for the old call signature."""
    return klines(coin, interval, limit)


def binance_24h(coin):
    j = get_json(f"{BINANCE}/api/v3/ticker/24hr", {"symbol": f"{coin}USDT"})
    return {"price": float(j["lastPrice"]), "chg_pct": float(j["priceChangePercent"]),
            "quote_vol": float(j["quoteVolume"])}


def binance_aggtrades(coin, limit=1000):
    """Recent trades. NOTE: 1000 aggTrades on BTC spans ~143 SECONDS -- far too
    short to characterise positioning. Kept only for a spot-check of the very
    latest tape; all flow metrics now come from 1m klines (see orderflow.py)."""
    j = get_json(f"{BINANCE}/api/v3/aggTrades", {"symbol": f"{coin}USDT", "limit": limit})
    df = pd.DataFrame(j)
    if df.empty:
        return df
    df["p"] = df["p"].astype(float); df["q"] = df["q"].astype(float)
    df["usd"] = df["p"] * df["q"]
    df["buy"] = ~df["m"]                     # m=True => buyer is maker => SELL aggressor
    df["ts"] = pd.to_datetime(df["T"].astype("int64"), unit="ms", utc=True)
    return df


def tape_span_s(agg):
    """How many seconds of tape a trades pull actually covers (honesty helper)."""
    if agg is None or agg.empty or "ts" not in agg:
        return None
    return float((agg["ts"].max() - agg["ts"].min()).total_seconds())


# ---------- cross-exchange price ----------
def coinbase_price(coin):
    try:
        j = get_json(f"{COINBASE}/products/{coin}-USD/ticker", tries=1, timeout=6)
        return float(j["price"])
    except Exception:
        return None

def okx_price(coin):
    try:
        j = get_json(f"{OKX}/api/v5/market/ticker", {"instId": f"{coin}-USDT"}, tries=1, timeout=5)
        return float(j["data"][0]["last"])
    except Exception:
        return None


def multi_volume(coin):
    """Aggregate 24h quote volume across exchanges (breadth of the venue)."""
    vols = {}
    try: vols["binance"] = binance_24h(coin)["quote_vol"]
    except Exception: pass
    try:
        j = get_json(f"{OKX}/api/v5/market/ticker", {"instId": f"{coin}-USDT"}, tries=1, timeout=5)
        vols["okx"] = float(j["data"][0]["volCcy24h"])
    except Exception: pass
    try:
        j = get_json(f"{COINBASE}/products/{coin}-USD/stats", tries=1, timeout=6)
        s = get_json(f"{COINBASE}/products/{coin}-USD/ticker", tries=1, timeout=6)
        vols["coinbase"] = float(j["volume"]) * float(s["price"])
    except Exception: pass
    return vols


# ---------- Binance futures derivatives ----------
def funding_rate(coin):
    try:
        j = get_json(f"{BINANCE_F}/fapi/v1/premiumIndex", {"symbol": f"{coin}USDT"}, tries=2, timeout=8)
        return float(j["lastFundingRate"])
    except Exception:
        return None

def open_interest_change(coin):
    """24h OI % change from hourly OI history."""
    try:
        j = get_json(f"{BINANCE_F}/futures/data/openInterestHist",
                     {"symbol": f"{coin}USDT", "period": "1h", "limit": 25}, tries=2, timeout=8)
        v = [float(x["sumOpenInterest"]) for x in j]
        if len(v) < 2 or v[0] == 0: return None
        return (v[-1] - v[0]) / v[0] * 100
    except Exception:
        return None

def long_short_ratio(coin):
    try:
        j = get_json(f"{BINANCE_F}/futures/data/globalLongShortAccountRatio",
                     {"symbol": f"{coin}USDT", "period": "1h", "limit": 1}, tries=2, timeout=8)
        return float(j[-1]["longShortRatio"])
    except Exception:
        return None

def top_trader_ls(coin):
    """Top-trader (large accounts) long/short POSITION ratio -- 'smart money' lean. Free."""
    try:
        j = get_json(f"{BINANCE_F}/futures/data/topLongShortPositionRatio",
                     {"symbol": f"{coin}USDT", "period": "1h", "limit": 1}, tries=2, timeout=8)
        return float(j[-1]["longShortRatio"])
    except Exception:
        return None

def taker_ls(coin):
    """Futures taker buy/sell volume ratio -- aggressive futures flow (>1 buyers). Free."""
    try:
        j = get_json(f"{BINANCE_F}/futures/data/takerlongshortRatio",
                     {"symbol": f"{coin}USDT", "period": "1h", "limit": 1}, tries=2, timeout=8)
        return float(j[-1]["buySellRatio"])
    except Exception:
        return None
