"""OGE: Donald J. Trump OGE Form 278-T (scanned PDFs -> OCR)."""
import io, re, json, hashlib, difflib, datetime as dt
from urllib.parse import urljoin, unquote
from bs4 import BeautifulSoup
import pdfplumber
from .http import get
from .config import OGE_INDEX_URLS, OGE_FILER_KEYWORDS, OGE_FORM_KEYWORDS, ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from .amounts import parse_amount

def list_filings():
    seen, out = set(), []
    for idx in OGE_INDEX_URLS:
        soup = BeautifulSoup(get(idx).text, "html.parser")
        for a in soup.find_all("a", href=True):
            url = urljoin(idx, a["href"])
            hay = (unquote(url) + " " + a.get_text(" ")).lower()
            if not url.lower().split("?")[0].endswith(".pdf") and "$file" not in hay:
                continue
            if not any(k in hay for k in OGE_FILER_KEYWORDS) or not any(k in hay for k in OGE_FORM_KEYWORDS):
                continue
            if url in seen:
                continue
            seen.add(url)
            out.append(dict(source="oge", doc_id="oge-" + hashlib.sha1(url.encode()).hexdigest()[:16],
                            filer="Donald J. Trump", filed_date=_date_from_name(unquote(url)), url=url))
    return out

def _date_from_name(name):
    m = re.search(r"(\d{1,2})[.\-](\d{1,2})[.\-](\d{2,4})", name.rsplit("/", 1)[-1])
    if not m:
        return None
    mo, d, y = map(int, m.groups())
    y = y + 2000 if y < 100 else y
    try:
        return dt.date(y, mo, d).isoformat()
    except ValueError:
        return None

# ---------- text extraction ----------
def extract_text(pdf_bytes):
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    if len(re.findall(r"\$\s?\d", text)) >= 3:
        return text
    # scanned -> OCR
    from pdf2image import convert_from_bytes
    import pytesseract
    pages = convert_from_bytes(pdf_bytes, dpi=300)
    return "\n".join(pytesseract.image_to_string(p, config="--psm 6") for p in pages)

# ---------- parsing ----------
TX_WORDS = {"purchase": "purchase", "sale": "sale", "exchange": "exchange", "sale (partial)": "sale_partial"}
DATE_TOK = r"[\dBOoIl|]{1,5}/[\dBOoIl|]{1,2}/?[\dBOoIl|]{0,4}|[\dBOoIl|]{3,5}/[\dBOoIl|]{4}"
ROW = re.compile(
    rf"^\s*(?P<n>\d{{1,4}})\.?\s+(?P<desc>.+?)\s+(?P<type>\S{{3,12}}(?:\s*\(partial\))?)\s+"
    rf"(?P<date>{DATE_TOK})\s+(?:(?P<late>\S{{2,4}})\s+)?(?P<amt>(?:over\s*)?\$.*)$", re.I)

def _fix_type(tok):
    t = re.sub(r"[^a-z()]", "", tok.lower()).replace("o", "e")
    if "partial" in t:
        return "sale_partial"
    best = difflib.get_close_matches(t, ["purchase", "sale", "exchange"], n=1, cutoff=0.55)
    return TX_WORDS.get(best[0]) if best else None

def _fix_date(tok):
    t = tok.translate(str.maketrans({"B": "8", "O": "0", "o": "0", "I": "1", "l": "1", "|": "1"}))
    if t.count("/") == 2:
        mo, d, y = t.split("/")
    else:  # OCR ate a slash, typically read as '1': 4117/2026 -> 4/17/2026
        md, y = t.split("/")[0], t.split("/")[-1]
        cands = []
        for i in range(1, len(md) - 1):
            if md[i] == "1":
                mo, d = md[:i], md[i + 1:]
                if 1 <= int(mo) <= 12 and 1 <= int(d) <= 31:
                    cands.append((mo, d))
        if not cands:
            return None
        mo, d = cands[0]
    try:
        y = int(y); y = y + 2000 if y < 100 else y
        return dt.date(y, int(mo), int(d)).isoformat()
    except (ValueError, TypeError):
        return None

def parse_text(text, filing):
    txs = []
    for line in text.splitlines():
        m = ROW.match(line)
        if not m:
            continue
        typ = _fix_type(m["type"])
        date = _fix_date(m["date"])
        low, high = parse_amount(m["amt"])
        if not (typ and date and low):
            continue
        txs.append(_tx(filing, m["desc"], typ, date, low, high, m["amt"], line))
    if ANTHROPIC_API_KEY and _looks_incomplete(text, txs):
        llm = llm_parse(text, filing)
        if len(llm) > len(txs):
            return llm
    return txs

def _looks_incomplete(text, txs):
    return len(txs) < 0.8 * len(re.findall(r"\$\s?[\d,. ]{4,}\s*[-•]", text))

def _tx(filing, desc, typ, date, low, high, amt_text, raw):
    desc = re.sub(r"\s+", " ", desc).strip(" .-|")
    return dict(doc_id=filing["doc_id"], filer=filing["filer"], owner="self", asset=desc, ticker=None,
                ticker_confidence=None, asset_class=classify(desc), tx_type=typ, tx_date=date,
                amount_low=low, amount_high=high, amount_text=amt_text.strip(), raw=raw[:500])

BOND_HINT = re.compile(r"\d+(\.\d+)?\s*%|\bdue\b|\b(bd|bds|bond|notes?|rev|ref|gen oblig|go|muni|dtd|cpn|mat)\b|\b20[3-6]\d\b", re.I)
def classify(desc):
    if re.search(r"\b(call|put)\b", desc, re.I):
        return "option"
    if re.search(r"\b(etf|trust|fund|spdr|ishares)\b", desc, re.I):
        return "etf_fund"
    return "bond" if BOND_HINT.search(desc) else "stock"

# ---------- optional: Claude cleans up garbled OCR ----------
def llm_parse(text, filing):
    import requests
    prompt = ("Below is OCR text from an OGE Form 278-T. Extract every transaction row. "
              "Fix obvious OCR errors (e.g. 'lourchase'->purchase, '4117/2026'->4/17/2026, 'Vos'->Yes). "
              "Return ONLY a JSON array, no prose, of objects with keys: description, type "
              "(purchase|sale|sale_partial|exchange), date (YYYY-MM-DD), amount (as written, e.g. '$1,000,001 - $5,000,000').\n\n"
              + text[:150_000])
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=300, headers={
        "x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": ANTHROPIC_MODEL, "max_tokens": 16000, "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    out = "".join(b.get("text", "") for b in r.json()["content"])
    rows = json.loads(re.sub(r"```(json)?", "", out).strip())
    txs = []
    for row in rows:
        low, high = parse_amount(row.get("amount", ""))
        if row.get("type") in TX_WORDS.values() and row.get("date") and low:
            txs.append(_tx(filing, row["description"], row["type"], row["date"], low, high, row["amount"], "llm:" + json.dumps(row)))
    return txs
