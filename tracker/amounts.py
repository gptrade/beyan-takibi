import re

# Standard congressional / OGE value brackets (lower, upper); upper None = open-ended
BRACKETS = [(1_001, 15_000), (15_001, 50_000), (50_001, 100_000), (100_001, 250_000),
            (250_001, 500_000), (500_001, 1_000_000), (1_000_001, 5_000_000),
            (5_000_001, 25_000_000), (25_000_001, 50_000_000), (50_000_001, None)]

def parse_amount(text: str):
    """Robust to OCR noise like '$1 000 001 • $5.000 000' or 'Over $50,000,000'."""
    t = text.replace("•", "-").replace("—", "-").replace("–", "-")
    if re.search(r"over", t, re.I):
        n = _num(t)
        return (n + 1, None) if n else (None, None)
    parts = t.split("-", 1)
    low = _num(parts[0])
    if low is None:
        return None, None
    best = min(BRACKETS, key=lambda b: abs(b[0] - low))   # snap to a standard bracket
    if abs(best[0] - low) / best[0] < 0.05:
        return best
    high = _num(parts[1]) if len(parts) > 1 else None
    return low, high

def _num(s):
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None

def fmt_amount(low, high):
    if low is None:
        return "?"
    if high is None:
        return f"> ${low-1:,}"
    return f"${low:,} – ${high:,}"
