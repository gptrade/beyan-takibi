"""Daily run:  python -m tracker.main [--silent] [--years 2025 2026] [--export]"""
import argparse, json, traceback
from . import house, oge, db, tickers, prices, notify

def process(con, filing, silent):
    pdf = house_or_oge_get(filing["url"])
    if filing["source"] == "house":
        txs = house.parse_pdf(pdf, filing)
    else:
        txs = oge.parse_text(oge.extract_text(pdf), filing)
        for t in txs:
            if t["asset_class"] in ("stock", "option", "etf_fund"):
                t["ticker"], t["ticker_confidence"] = tickers.lookup(t["asset"])
    status = "ok" if txs else "empty"            # 'empty' is retried next run (e.g. OCR/format issue)
    db.save_filing(con, filing, txs, status)
    print(f"[{filing['source']}] {filing['doc_id']} {filing.get('filed_date')} -> {len(txs)} tx ({status})")
    if txs and not silent:
        notify.send(notify.format_filing(filing, txs, prices.perf))
    elif not txs and not silent:
        notify.send(f"⚠️ {filing['filer']} için yeni beyan bulundu ama ayrıştırılamadı:\n{filing['url']}")

def house_or_oge_get(url):
    from .http import get
    return get(url).content

def run(silent=False, years=None):
    with db.connect() as con:
        known = db.known_doc_ids(con)
        sources = [("house", lambda: house.list_filings(years)), ("oge", oge.list_filings)]
        for name, lister in sources:
            try:
                filings = lister()
            except Exception as e:
                notify.send(f"⚠️ {name} kaynağı okunamadı: {e}"); continue
            for f in sorted(filings, key=lambda f: f.get("filed_date") or ""):
                if f["doc_id"] in known:
                    continue
                try:
                    process(con, f, silent)
                    con.commit()
                except Exception:
                    traceback.print_exc()

def export(path="site/data.json"):
    """Write everything the web page needs into one JSON file."""
    import os, datetime as dt
    with db.connect() as con:
        filings = [dict(r) for r in con.execute("SELECT * FROM filings ORDER BY filed_date DESC")]
        rows = [dict(r) for r in con.execute(
            "SELECT t.*, f.filed_date, f.url, f.source FROM transactions t JOIN filings f USING(doc_id) "
            "ORDER BY t.tx_date DESC")]
    for r in rows:
        r.pop("raw", None)
        r["perf"] = prices.perf(r["ticker"], r["tx_date"]) if r["asset_class"] in ("stock", "option", "etf_fund") else None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = dict(generated_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               filings=filings, transactions=rows)
    json.dump(out, open(path, "w"), default=str)
    print(f"exported {len(rows)} rows -> {path}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--silent", action="store_true", help="backfill without Telegram messages")
    ap.add_argument("--years", type=int, nargs="*")
    ap.add_argument("--export", action="store_true")
    a = ap.parse_args()
    run(a.silent, a.years)
    if a.export:
        export()
