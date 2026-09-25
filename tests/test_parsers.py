from tracker import house, oge
from tracker.amounts import parse_amount

F = dict(doc_id="t", filer="x", url="u", source="t")

def test_amount_ocr_noise():
    assert parse_amount("$1 000 001 • $5 000 000") == (1_000_001, 5_000_000)
    assert parse_amount("$1,000 001 -$5.000 000") == (1_000_001, 5_000_000)
    assert parse_amount("$250 001 • $500 000") == (250_001, 500_000)
    assert parse_amount("Over $50,000,000") == (50_000_001, None)

HOUSE = """Filing ID #20026000
ID Owner Asset Transaction Type Date Notification Date Amount Cap. Gains > $200?
SP Alphabet Inc. - Class A Common
Stock (GOOGL) [ST] P 01/14/2026 01/14/2026 $1,000,001 -
$5,000,000
F S: New
SP NVIDIA Corporation - Common Stock (NVDA) [OP] P 01/16/2026 01/16/2026 $500,001 - $1,000,000
F S: New
D: Purchased 50 call options with a strike price of $80 and an expiration date of 1/15/27.
SP Visa Inc. (V) [ST] S (partial) 01/20/2026 01/21/2026 $15,001 - $50,000
"""
def test_house():
    t = house.parse_text(HOUSE, F)
    assert [x["ticker"] for x in t] == ["GOOGL", "NVDA", "V"]
    assert t[0]["asset"] == "Alphabet Inc. - Class A Common Stock" and t[0]["owner"] == "SP"
    assert t[0]["amount_low"] == 1_000_001 and t[0]["amount_high"] == 5_000_000
    assert t[1]["asset_class"] == "option" and "call options" in t[1]["asset"]
    assert t[2]["tx_type"] == "sale_partial" and t[2]["tx_date"] == "2026-01-20"

# Real OCR output from Trump's 06.25.2026 278-T
OGE = """67 UNITEDHEALTH GROUP INC lourchase 4117/2026 Vos $1 000 001 - $5 000 000
68 VERJSKANALYTICS INC. lourchaso 4117/2026 Yes $250 001 - $500 000
70 VICI P~rties Inc. lourchaso 4/17/2026 Vos $100 001 - $250 000
71 VISA INC-CLASS A SHARES salo 4117/2026 Vos $1,000 001 -$5.000 000
72 WASTE MGMT INC DEL I N rchaso 4117/2026 Yes $100,001 -$250 000
73 WORKDAY INCCL A salo 4117/2026 Yes $1 000 001 • $5 000 000
74 3MCO lru•rchase 4127/2026 Vos $15 001 -$50 000
76 ABBOTT LABORATORIES salo 4127/2026 Vos $100 001 - $250 000
12 CALIFORNIA ST GO BDS 5.000% 03/01/2045 purchase 4/17/2026 Yes $250,001 - $500,000
"""
def test_oge_ocr():
    t = oge.parse_text(OGE, F)
    assert len(t) == 9
    assert t[0]["tx_type"] == "purchase" and t[0]["tx_date"] == "2026-04-17"
    assert t[3]["asset"].startswith("VISA") and t[3]["tx_type"] == "sale"
    assert t[3]["amount_low"] == 1_000_001
    assert t[6]["tx_date"] == "2026-04-27" and t[6]["amount_low"] == 15_001
    assert t[8]["asset_class"] == "bond" and t[0]["asset_class"] == "stock"
