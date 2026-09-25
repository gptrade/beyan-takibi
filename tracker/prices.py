import datetime as dt, functools
import yfinance as yf

@functools.lru_cache(maxsize=512)
def history(ticker, start):
    s = dt.date.fromisoformat(start) - dt.timedelta(days=7)
    df = yf.download(ticker.replace(".", "-"), start=s.isoformat(), progress=False, auto_adjust=True)
    return df["Close"].squeeze() if not df.empty else None

def perf(ticker, tx_date):
    """Close on/just before the trade date, latest close, % change."""
    if not ticker or not tx_date:
        return None
    try:
        c = history(ticker, tx_date)
        if c is None or c.empty:
            return None
        on = c[c.index <= tx_date]
        p0 = float(on.iloc[-1]) if not on.empty else float(c.iloc[0])
        p1 = float(c.iloc[-1])
        return dict(tx_close=p0, last_close=p1, last_date=c.index[-1].date().isoformat(), chg=p1 / p0 - 1)
    except Exception:
        return None
