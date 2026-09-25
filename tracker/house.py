"""House Clerk: Nancy Pelosi (and any other member) Periodic Transaction Reports."""
import io, re, zipfile, datetime as dt
import xml.etree.ElementTree as ET
import pdfplumber
from .http import get
from .config import HOUSE_INDEX_ZIP, HOUSE_PTR_PDF, HOUSE_MEMBERS
from .amounts import parse_amount

def list_filings(years=None):
    years = years or sorted({dt.date.today().year, dt.date.today().year - 1})
    out = []
    for y in years:
        z = zipfile.ZipFile(io.BytesIO(get(HOUSE_INDEX_ZIP.format(year=y)).content))
        xml_name = next(n for n in z.namelist() if n.lower().endswith(".xml"))
        root = ET.fromstring(z.read(xml_name))
        for m in root.iter("Member"):
            g = lambda k: (m.findtext(k) or "").strip()
            if g("FilingType") != "P":          # P = Periodic Transaction Report
                continue
            if not any(g("Last").lower() == l.lower() and g("First").lower().startswith(f.lower())
                       for l, f in HOUSE_MEMBERS):
                continue
            doc = g("DocID")
            out.append(dict(source="house", doc_id=f"house-{doc}", filer=f'{g("First")} {g("Last")}',
                            filed_date=_iso(g("FilingDate")), url=HOUSE_PTR_PDF.format(year=y, doc_id=doc)))
    return out

# Typical e-filed row: "SP Apple Inc. - Common Stock (AAPL) [ST] P 01/15/2026 01/16/2026 $1,000,001 - $5,000,000"
ROW = re.compile(
    r"(?P<asset>[^\[\]$]{2,300}?)\s*\((?P<ticker>[A-Z][A-Z0-9.\-]{0,6})\)\s*"
    r"\[(?P<kind>[A-Z]{2})\]\s*"
    r"(?P<type>S\s*\(partial\)|P|S|E)\s+"
    r"(?P<tx>\d{2}/\d{2}/\d{4})\s+(?P<notif>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<amt>Over\s+\$[\d,]+|\$[\d,]+\s*-\s*\$[\d,]+|\$[\d,]+)")
TYPES = {"P": "purchase", "S": "sale", "E": "exchange"}
KIND = {"ST": "stock", "OP": "option", "GS": "gov_bond", "CS": "corp_bond", "EF": "etf", "MF": "fund"}

def parse_pdf(pdf_bytes, filing):
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    return parse_text(text, filing)

def parse_text(text, filing):
    text = text.replace("\x00", "")
    flat = re.sub(r"[ \t]+", " ", text)
    flat = re.sub(r"-\s*\n\s*\$", "- $", flat)           # amount split over two lines
    txs = []
    for m in ROW.finditer(flat):
        owner, asset = _clean_asset(m["asset"])
        # option details live on the following "D:" description line
        tail = re.split(r"\[[A-Z]{2}\]", flat[m.end(): m.end() + 600])[0]  # stop at next row
        desc = re.search(r"\bD\s*:\s*([^\n]+)", tail)
        low, high = parse_amount(m["amt"])
        typ = "sale_partial" if "partial" in m["type"] else TYPES[m["type"][0]]
        kind = KIND.get(m["kind"], m["kind"].lower())
        if desc and re.search(r"\b(call|put)\s+option", desc.group(1), re.I):
            kind = "option"
        txs.append(dict(doc_id=filing["doc_id"], filer=filing["filer"], owner=owner,
                        asset=asset + (f" — {desc.group(1).strip()}" if desc and kind == "option" else ""),
                        ticker=m["ticker"], ticker_confidence=1.0, asset_class=kind, tx_type=typ,
                        tx_date=_iso(m["tx"]), amount_low=low, amount_high=high,
                        amount_text=m["amt"], raw=m.group(0)[:500]))
    return txs

META = re.compile(r"^\s*(F\s*S|S\s*O|D|C|L)\s*:|Filing ID|Owner\s+Asset|Notification|Cap\.|Gains|^\s*ID\b|\$200", re.I)

def _clean_asset(raw):
    lines = [l.strip() for l in raw.split("\n") if l.strip() and not META.search(l)]
    lines = lines[-2:]  # asset names wrap at most onto a second line
    owner = "self"
    for i, l in enumerate(lines):
        mo = re.match(r"^(SP|JT|DC)\s+(.*)", l)
        if mo:
            owner, lines = mo.group(1), [mo.group(2)] + lines[i + 1:]
            break
    return owner, " ".join(lines).strip(" -")

def _iso(d):
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return dt.datetime.strptime(d.strip(), fmt).date().isoformat()
        except (ValueError, AttributeError):
            pass
    return None
