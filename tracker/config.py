import os

HTTP_UA = os.getenv("SEC_USER_AGENT", "DisclosureTracker/1.0 (your-email@example.com)")  # SEC requires a real contact
DB_PATH = os.getenv("TRACKER_DB", "data/tracker.db")

# --- House (Pelosi) ---
HOUSE_INDEX_ZIP = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
HOUSE_PTR_PDF = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"
HOUSE_MEMBERS = [("Pelosi", "Nancy")]  # (Last, First) — add more members here

# --- OGE (Trump) ---
# Presidential & VP filings view on OGE. Any page that links the PDFs works; comma-separate several.
OGE_INDEX_URLS = [u for u in os.getenv(
    "OGE_INDEX_URLS", "https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index?OpenView&Count=1000").split(",") if u]
OGE_FILER_KEYWORDS = ["trump"]
OGE_FORM_KEYWORDS = ["278t", "278-t", "278 t", "278%20t", "278-t%20", "periodic"]

# --- Notifications ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- Optional LLM cleanup of OCR text (Trump's 278-Ts are scanned) ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
