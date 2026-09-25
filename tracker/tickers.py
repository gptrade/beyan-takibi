"""Map OGE company names ('VISA INC-CLASS A SHARES') to tickers via SEC's public list."""
import json, os, re, difflib, functools
from .http import get

OVERRIDES_PATH = "data/ticker_overrides.json"   # {"NORMALIZED NAME": "TICKER"} for manual fixes
STOP = r"\b(INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|PLC|LLC|LP|NV|SA|AG|HOLDINGS?|GROUP|DEL|THE|" \
       r"COM|COMMON|STOCK|SHARES?|NEW|CL|CLASS|[A-C]|ADR|SPONSORED|ORD)\b"

def norm(name):
    n = name.upper().replace("&", " AND ")
    n = re.sub(r"[^A-Z0-9 ]", " ", n)
    n = re.sub(STOP, " ", n)
    return re.sub(r"\s+", " ", n).strip()

@functools.lru_cache(maxsize=1)
def _sec():
    data = get("https://www.sec.gov/files/company_tickers.json").json()
    table = {}
    for row in data.values():
        table.setdefault(norm(row["title"]), row["ticker"])   # first = primary share class
    return table

@functools.lru_cache(maxsize=1)
def _overrides():
    if os.path.exists(OVERRIDES_PATH):
        return {norm(k): v for k, v in json.load(open(OVERRIDES_PATH)).items()}
    return {}

def lookup(name):
    n = norm(name)
    if not n:
        return None, 0.0
    if n in _overrides():
        return _overrides()[n], 1.0
    t = {**_sec(), **_overrides()}
    if n in t:
        return t[n], 0.95
    m = difflib.get_close_matches(n, t.keys(), n=1, cutoff=0.88)
    if m:
        return t[m[0]], round(difflib.SequenceMatcher(None, n, m[0]).ratio(), 2)
    words = n.split()                      # OCR glue like 'WORKDAY INCCL' -> try 'WORKDAY'
    for k in range(len(words) - 1, 0, -1):
        pre = " ".join(words[:k])
        if len(pre) >= 4 and pre in t:
            return t[pre], 0.8
    return None, 0.0
