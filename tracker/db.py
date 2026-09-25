import sqlite3, os
from contextlib import contextmanager
from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS filings (
  doc_id TEXT PRIMARY KEY, source TEXT, filer TEXT, filed_date TEXT,
  url TEXT, status TEXT, n_tx INTEGER, processed_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, doc_id TEXT, filer TEXT, owner TEXT,
  asset TEXT, ticker TEXT, ticker_confidence REAL, asset_class TEXT,
  tx_type TEXT, tx_date TEXT, amount_low INTEGER, amount_high INTEGER,
  amount_text TEXT, raw TEXT, notified INTEGER DEFAULT 0,
  UNIQUE(doc_id, asset, tx_type, tx_date, amount_low));
"""

@contextmanager
def connect(path=None):
    path = path or DB_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    try:
        yield con
        con.commit()
    finally:
        con.close()

def known_doc_ids(con):
    return {r["doc_id"] for r in con.execute("SELECT doc_id FROM filings WHERE status='ok'")}

def save_filing(con, f, txs, status="ok"):
    con.execute("INSERT OR REPLACE INTO filings(doc_id,source,filer,filed_date,url,status,n_tx) VALUES (?,?,?,?,?,?,?)",
                (f["doc_id"], f["source"], f["filer"], f.get("filed_date"), f["url"], status, len(txs)))
    for t in txs:
        con.execute("""INSERT OR IGNORE INTO transactions
          (doc_id,filer,owner,asset,ticker,ticker_confidence,asset_class,tx_type,tx_date,amount_low,amount_high,amount_text,raw)
          VALUES (:doc_id,:filer,:owner,:asset,:ticker,:ticker_confidence,:asset_class,:tx_type,:tx_date,:amount_low,:amount_high,:amount_text,:raw)""", t)
