# Pelosi & Trump Disclosure Tracker

Checks official filings every weekday, parses new transactions, stores them in SQLite,
and sends a Telegram message when a new filing appears. Not investment advice.

| Filer | Source | Format | How it's parsed |
|---|---|---|---|
| Nancy Pelosi | House Clerk yearly index (`{year}FD.zip`) → PTR PDFs | e-filed, text PDF | regex (ticker is in the filing) |
| Donald J. Trump | OGE Presidential filings page → OGE Form 278-T PDFs | **scanned** | OCR (Tesseract) → fuzzy fixes → SEC name→ticker map; optional Claude pass when OCR is messy |

## Web sitesi olarak kurulum (bilgisayarında hiçbir şey çalışmaz)

Her şey GitHub'ın sunucularında çalışır: GitHub Actions günde üç kez (08:00, 17:00, 01:00 İstanbul)
beyanları kontrol eder, `site/data.json` dosyasını günceller ve GitHub Pages siteyi yeniden yayınlar.

1. github.com'da yeni bir repo aç (ör. `beyan-takibi`). Private repo'da Pages için ücretli plan gerekir;
   ücretsiz kullanacaksan **Public** seç (içerik zaten kamuya açık beyanlar).
2. "uploading an existing file" bağlantısıyla zip'in içindeki tüm dosya ve klasörleri sürükleyip commit et.
   `.github/workflows/daily.yml` dosyasının da yüklendiğinden emin ol (gizli klasör; Mac'te Cmd+Shift+. ile görünür).
3. **Settings → Pages → Source: GitHub Actions** seç.
4. **Settings → Secrets and variables → Actions** altında ekle:
   `SEC_USER_AGENT` (ör. `Gursah P. mail@adres.com`, zorunlu), isteğe bağlı `TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_CHAT_ID`, `ANTHROPIC_API_KEY`.
5. **Actions → disclosure-tracker → Run workflow** ile ilk çalıştırmayı başlat. İlk çalıştırma 2025–2026
   geçmişini Telegram'a mesaj atmadan doldurur.
6. Site adresi: `https://<kullanıcı-adın>.github.io/beyan-takibi/`. Telefondan da açılır.

Bir çalıştırma hata verirse sitenin üstünde "son kontrol 26 saatten eski" uyarısı çıkar; nedeni Actions sekmesindeki loglardadır.

## Local setup (optional)
```bash
pip install -r requirements.txt           # plus: apt install tesseract-ocr poppler-utils
export SEC_USER_AGENT="Your Name you@mail.com"
export TELEGRAM_BOT_TOKEN=...  TELEGRAM_CHAT_ID=...   # from @BotFather / getUpdates
python -m tracker.main --silent --years 2025 2026     # first run: backfill, no messages
python -m tracker.main --export                       # daily run; writes data/transactions.json
pytest -q                                              # parser tests (includes real OCR lines)
```
Without Telegram vars, messages are printed to stdout.

## Automate
Push to a private GitHub repo, add the secrets (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
`SEC_USER_AGENT`, optional `ANTHROPIC_API_KEY`), and `.github/workflows/daily.yml` runs twice
a day and commits `data/` so state persists. A plain cron job on a VPS works just as well.

## Tuning
- **Add members:** `HOUSE_MEMBERS` in `tracker/config.py`.
- **OGE page moved?** set `OGE_INDEX_URLS` (comma-separated) to any page linking the 278-T PDFs.
- **Wrong/missing ticker:** add `"COMPANY NAME": "TICKER"` to `data/ticker_overrides.json`.
- Filings that parse to zero rows are marked `empty` and retried on the next run, with a Telegram warning.
- `transactions.json` includes `perf` (close on trade date → latest close) for your portal's stock page.

## Caveats
- Amounts are **ranges**; trade dates can be up to 45 days before the filing.
- Trump's filings mostly list bonds; `asset_class` separates stocks/options/ETFs from bonds (heuristic).
- OCR is imperfect: check `ticker_confidence` < 0.9 rows, or enable the Claude pass.
