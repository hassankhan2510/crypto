"""Tiny resilient HTTP GET. Per-call `tries`/`timeout` so a slow or blocked
secondary venue can never stall the whole run (fail fast, degrade gracefully)."""
import time, requests
from config import HTTP_TIMEOUT, RETRIES

_session = requests.Session()
_session.headers.update({"User-Agent": "cryptointel/1.0"})

def get_json(url, params=None, tries=None, timeout=None):
    tries = tries or RETRIES
    timeout = timeout or HTTP_TIMEOUT
    last = None
    for i in range(tries):
        try:
            r = _session.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}: {r.text[:120]}"
        except Exception as e:
            last = str(e)[:120]
        if i < tries - 1:
            time.sleep(0.3 * (i + 1))
    raise RuntimeError(f"GET failed {url}: {last}")
