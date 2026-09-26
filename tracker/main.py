"""Run:  python -m tracker.main [--silent] [--years 2025 2026] [--export] [--test-telegram]"""
import argparse, json, sys, traceback, datetime as dt
from . import house, oge, db, tickers, prices, notify

def fetch(url):
    from .http import get
    return get(url).content

def process(con, filing, silent):
    pdf = fetch(filing["url"])
    if filing["source"] == "house":
        txs = house.parse_pdf(pdf, filing)
    else:
        txs = oge.parse_text(oge.extract_text(pdf), filing)
        for t in txs:
            if t["asset_class"] in ("stock", "option", "etf_fund"):
                t["ticker"], t["ticker_confidence"] = tickers.lookup(t["asset"])
    status = "ok" if txs else "empty"            # 'empty' is retried next run
    db.save_filing(con, filing, txs, status, notified=1 if silent else 0)
    con.commit()
    print(f"  YENİ [{filing['source']}] {filing['filer']} {filing.get('filed_date')} -> {len(txs)} işlem ({status})")

def announce_pending(con):
    """Send every filing whose message hasn't been delivered yet. A failed send is retried next run."""
    for f in db.pending(con):
        txs = db.txs_for(con, f["doc_id"])
        text = (notify.format_filing(f, txs, prices.perf) if txs else
                f"⚠️ {f['filer']} için yeni beyan bulundu ama ayrıştırılamadı:\n{f['url']}")
        try:
            if notify.send(text):
                db.mark_notified(con, f["doc_id"]); con.commit()
                print(f"  Telegram'a gönderildi: {f['filer']} {f.get('filed_date')}")
        except notify.TelegramError as e:
            print(f"::error::Telegram mesajı gönderilemedi ({e}). Bir sonraki çalıştırmada tekrar denenecek.")

def run(silent=False, years=None):
    print(f"Telegram: {'AYARLI' if notify.configured() else 'AYARLI DEĞİL (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID secret eksik)'}")
    print("Mod: " + ("İLK KURULUM, geçmiş sessizce yükleniyor" if silent else "normal, yeni beyanlar bildirilecek"))
    new = 0
    with db.connect() as con:
        known = db.known_doc_ids(con)
        for name, lister in [("house", lambda: house.list_filings(years)), ("oge", oge.list_filings)]:
            try:
                filings = lister()
                print(f"{name}: {len(filings)} beyan listelendi")
            except Exception as e:
                print(f"::warning::{name} kaynağı okunamadı: {e}")
                try: notify.send(f"⚠️ {name} kaynağı okunamadı: {e}")
                except notify.TelegramError: pass
                continue
            for f in sorted(filings, key=lambda f: f.get("filed_date") or ""):
                if f["doc_id"] in known:
                    continue
                try:
                    process(con, f, silent); new += 1
                except Exception:
                    traceback.print_exc()
        if silent:
            n_f = con.execute("SELECT COUNT(*) FROM filings").fetchone()[0]
            n_t = con.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
            try:
                notify.send(f"✅ <b>Beyan Takibi kuruldu</b>\n{n_f} geçmiş beyan, {n_t} işlem yüklendi. "
                            f"Bundan sonra yeni beyanlar buraya gelecek.")
            except notify.TelegramError as e:
                print(f"::error::Kurulum mesajı gönderilemedi ({e})")
        else:
            announce_pending(con)
    print(f"Sonuç: {new} yeni beyan" + ("" if new else " (bildirilecek bir şey yok, bu normal)"))

def test_telegram():
    if not notify.configured():
        print("::error::TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID secret'ı tanımlı değil ya da adı yanlış yazılmış.")
        sys.exit(1)
    try:
        notify.send("🔔 <b>Test mesajı</b>\nBeyan Takibi Telegram bağlantısı çalışıyor. "
                    + dt.datetime.now().strftime("%d.%m.%Y %H:%M UTC"))
        print("Test mesajı gönderildi.")
    except notify.TelegramError as e:
        hint = ""
        m = str(e).lower()
        if "chat not found" in m:   hint = " → TELEGRAM_CHAT_ID yanlış, ya da bota henüz Başlat/Start ile mesaj atılmadı."
        elif "unauthorized" in m or "401" in m: hint = " → TELEGRAM_BOT_TOKEN yanlış ya da eksik kopyalanmış."
        elif "blocked" in m:        hint = " → Botu Telegram'da engellemişsin; engeli kaldırıp Başlat'a bas."
        print(f"::error::{e}{hint}")
        sys.exit(1)

def export(path="site/data.json"):
    """Write everything the web page needs into one JSON file."""
    import os
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
    ap.add_argument("--silent", action="store_true", help="backfill without per-filing Telegram messages")
    ap.add_argument("--years", type=int, nargs="*")
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--test-telegram", action="store_true")
    a = ap.parse_args()
    if a.test_telegram:
        test_telegram(); sys.exit(0)
    run(a.silent, a.years)
    if a.export:
        export()
