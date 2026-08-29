"""Tiny resilient HTTP GET (retries, timeout, JSON)."""
import time, requests
from config import HTTP_TIMEOUT, RETRIES

_session = requests.Session()
_session.headers.update({"User-Agent": "cryptointel/1.0"})

def get_json(url, params=None):
    last = None
    for i in range(RETRIES):
        try:
            r = _session.get(url, params=params, timeout=HTTP_TIMEOUT)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}: {r.text[:120]}"
        except Exception as e:
            last = str(e)[:120]
        time.sleep(0.4 * (i + 1))
    raise RuntimeError(f"GET failed {url}: {last}")
