import time, requests
from .config import HTTP_UA

S = requests.Session()
S.headers.update({"User-Agent": HTTP_UA})

def get(url, retries=3, **kw):
    for i in range(retries):
        try:
            r = S.get(url, timeout=60, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if i == retries - 1:
                raise
            time.sleep(2 ** i * 3)
