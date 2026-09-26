import html, requests
from .config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from .amounts import fmt_amount

EMOJI = {"purchase": "🟢 Alım", "sale": "🔴 Satım", "sale_partial": "🟠 Kısmi satım", "exchange": "🔁 Takas"}

def format_filing(f, txs, perf_fn=None, max_rows=25):
    eq = [t for t in txs if t["asset_class"] in ("stock", "option", "etf_fund")]
    lines = [f"<b>📄 Yeni beyan: {html.escape(f['filer'])}</b>",
             f"Beyan tarihi: {f.get('filed_date') or '?'} · {len(txs)} işlem ({len(eq)} hisse/opsiyon)",
             f'<a href="{html.escape(f["url"])}">Kaynak PDF</a>', ""]
    for t in sorted(eq, key=lambda t: -(t["amount_low"] or 0))[:max_rows]:
        tk = t["ticker"] or "?"
        p = perf_fn(t["ticker"], t["tx_date"]) if perf_fn and t["ticker"] else None
        ps = f" · {p['chg']:+.1%} işlemden beri" if p else ""
        lines.append(f"{EMOJI.get(t['tx_type'], t['tx_type'])} <b>{html.escape(tk)}</b> "
                     f"{html.escape(t['asset'][:60])}\n   {t['tx_date']} · {fmt_amount(t['amount_low'], t['amount_high'])}{ps}")
    if len(eq) > max_rows:
        lines.append(f"… +{len(eq) - max_rows} daha")
    lines.append("\n<i>Yatırım tavsiyesi değildir.</i>")
    return "\n".join(lines)

def configured():
    return bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)

def _chunks(text, limit=3800):
    out, cur = [], ""
    for line in text.split("\n"):
        if cur and len(cur) + len(line) + 1 > limit:
            out.append(cur); cur = ""
        cur = (cur + "\n" + line) if cur else line
    return out + ([cur] if cur else [])

class TelegramError(RuntimeError):
    pass

def send(text):
    """Send to Telegram. Returns False if not configured; raises TelegramError with Telegram's reason on failure."""
    if not configured():
        print("[telegram kapalı] " + text.replace("\n", " | ")[:300])
        return False
    for chunk in _chunks(text):
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", timeout=30,
                          json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "HTML",
                                "disable_web_page_preview": True})
        if not r.ok:
            try:
                reason = r.json().get("description", r.text)
            except ValueError:
                reason = r.text
            raise TelegramError(f"Telegram {r.status_code}: {reason}")
    return True
