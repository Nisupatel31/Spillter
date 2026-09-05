"""
Receipt Parser Module for Spillter
Extracts structured expense details from OCR text and UPI payment screenshots:
- Total Amount
- Merchant / Store / Vendor Name
- Date
- Category (Food, Stay, Travel, Activities, etc.)
- Payment Mode (UPI, Cash, Credit Card, Debit Card, Net Banking)
"""

import re
from datetime import datetime
from typing import Dict, Any, Optional


CATEGORY_KEYWORDS = {
    "Food": [
        "restaurant", "cafe", "coffee", "bistro", "dhaba", "bar", "pub", "grill",
        "kitchen", "dining", "food", "lunch", "dinner", "breakfast", "burger",
        "pizza", "biryani", "bakery", "sweets", "swiggy", "zomato", "cocktails",
        "brewery", "shack", "meals", "beverage", "snack", "wharf", "fisherman",
        "seafood", "drinks", "lounge", "salad", "calamari", "pasta", "curry",
        "paneer", "chicken", "naan", "rice", "dessert", "starter"
    ],
    "Stay": [
        "hotel", "resort", "villa", "stay", "lodge", "homestay", "inn", "hostel",
        "guest house", "room", "checkin", "check-in", "checkout", "airbnb",
        "accommodation", "cottage"
    ],
    "Travel": [
        "fuel", "petrol", "diesel", "hp petrol", "indian oil", "bharat petroleum",
        "toll", "fastag", "cab", "taxi", "uber", "ola", "flight", "airline",
        "indigo", "air india", "train", "irctc", "railway", "railways", "uts",
        "indian railways", "bus", "redbus", "parking", "auto", "metro", "driver"
    ],
    "Activities": [
        "scuba", "diving", "watersport", "water sport", "jet ski", "parasailing",
        "paragliding", "rafting", "trekking", "safari", "adventure", "camp",
        "cruise", "bungee", "kayak", "snorkeling"
    ],
    "Sightseeing": [
        "ticket", "tickets", "entry fee", "monument", "fort", "palace", "museum",
        "sanctuary", "zoo", "aquarium", "temple", "guide", "heritage", "viewpoint"
    ],
    "Shopping": [
        "mart", "supermarket", "store", "mall", "clothing", "bazaar", "market",
        "souvenir", "apparel", "retail", "decathlon", "lifestyle", "handicrafts"
    ]
}

MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12"
}


def clean_number(num_str: str) -> Optional[float]:
    """Helper to sanitize and convert string to float."""
    try:
        sanitized = re.sub(r"[^\d.]", "", num_str.replace(",", ""))
        val = float(sanitized)
        return val if val > 0 else None
    except Exception:
        return None


def normalize_ocr_rupee_misrecognitions(text: str) -> str:
    """
    Tesseract English models lack the Indian Rupee symbol (₹, U+20B9).
    OCR engines frequently misidentify '₹' as the digit '2' or 'Z' or '7'.
    This function normalizes those artifacts before extracting the amounts.
    """
    # 1. Single digit 2 followed by space and numbers (e.g. '2 77.60', '2 500.00', '2 2,450.00') -> '₹ \1'
    text = re.sub(r'(?:^|(?<=\s))2\s+([0-9]+(?:\.[0-9]{1,2})?)', r'₹ \1', text)

    # 2. 'Payment of 2...' in Google Pay / UPI (e.g. 'Payment of 277.60 completed' -> 'Payment of ₹ 77.60 completed')
    text = re.sub(r'(payment\s+of\s+)2([0-9]+(?:\.[0-9]{1,2})?)', r'\1₹ \2', text, flags=re.IGNORECASE)

    # 3. 'Paid 2...' in UPI (e.g. 'Paid 2500' -> 'Paid ₹ 500')
    text = re.sub(r'(paid(?:\s+to[^\n\r]+?)?\s+)2([0-9]+(?:\.[0-9]{1,2})?)', r'\1₹ \2', text, flags=re.IGNORECASE)

    # 4. GPay specific block:
    # To <Merchant>
    # 277.60 (misread ₹77.60)
    # Completed
    lines = text.splitlines()
    for i in range(len(lines)):
        clean_l = lines[i].strip()
        if re.match(r'^(?:to|paid\s*to)\s+', clean_l, re.I) and i + 1 < len(lines):
            next_l = lines[i + 1].strip()
            gpay_amt_m = re.match(r'^2([0-9,]+(?:\.[0-9]{1,2})?)$', next_l)
            if gpay_amt_m:
                after_idx = i + 2
                is_gpay = False
                while after_idx < min(len(lines), i + 4):
                    if re.search(r'(?:completed|successful|202\d|\bjan\b|\bfeb\b|\bmar\b|\bapr\b|\bmay\b|\bjun\b|\bjul\b|\baug\b|\bsep\b|\boct\b|\bnov\b|\bdec\b)', lines[after_idx], re.I):
                        is_gpay = True
                        break
                    after_idx += 1
                if is_gpay:
                    lines[i + 1] = f"₹ {gpay_amt_m.group(1)}"
    return "\n".join(lines)


def extract_amount(text: str) -> float:
    """
    Extract total amount from receipt text.
    Gives precedence to 'Total', 'Grand Total', 'Paid', 'Payment of', 'Net Payable', and '₹' patterns.
    """
    # Normalize OCR Rupee misrecognitions (where ₹ is read as 2)
    normalized_text = normalize_ocr_rupee_misrecognitions(text)
    lines = normalized_text.splitlines()

    # 1. Look for high-confidence labelled totals
    high_priority_patterns = [
        r"(?:payment\s*of|paid\s*amount|amount\s*paid)\s*[:=-]?\s*(?:[₹rRsInR.\s]*)\s*([0-9,]+(?:\.[0-9]{1,2})?)",
        r"(?:grand\s*total|net\s*payable|total\s*amount|bill\s*amount|total\s*fare|fare)\s*[:=-]?\s*(?:[₹rRsInR.\s]*)\s*([0-9,]+(?:\.[0-9]{1,2})?)",
        r"(?:total|paid|amount)\s*[:=-]?\s*(?:[₹rRsInR.\s]*)\s*([0-9,]+(?:\.[0-9]{1,2})?)",
        r"[₹]\s*([0-9,]+(?:\.[0-9]{1,2})?)",
        r"(?:rs\.?|inr)\s*([0-9,]+(?:\.[0-9]{1,2})?)",
    ]

    for pat in high_priority_patterns:
        matches = re.findall(pat, normalized_text, re.IGNORECASE)
        if matches:
            candidates = []
            for m in matches:
                val = clean_number(m)
                if val is not None and val < 1000000:
                    candidates.append(val)
            if candidates:
                return max(candidates)

    # 2. UPI specific: line right after "Paid to <Merchant>" or "To <Merchant>" often has just ₹XXX or XXX
    for i, line in enumerate(lines):
        if re.search(r"\b(?:paid\s*to|to)\b", line, re.IGNORECASE) and i + 1 < len(lines):
            next_line = lines[i + 1]
            match = re.search(r"([₹rRsInR\s]*)([0-9,]+(?:\.[0-9]{1,2})?)", next_line)
            if match:
                val = clean_number(match.group(2))
                if val:
                    return val

    # 3. Fallback: Search any currency figures in the entire text
    all_numbers = re.findall(r"\b([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)\b", normalized_text)
    valid_nums = []
    for num in all_numbers:
        val = clean_number(num)
        if val and 5.0 <= val <= 200000.0:
            valid_nums.append(val)

    if valid_nums:
        return max(valid_nums)

    return 0.0


def extract_date(text: str) -> str:
    """
    Extract date in YYYY-MM-DD format. Defaults to today's date if not found.
    """
    today = datetime.now().strftime("%Y-%m-%d")

    # Pattern 1: YYYY-MM-DD
    match = re.search(r"\b(20\d{2})[-/.](0[1-9]|1[0-2])[-/.](0[1-9]|[12]\d|3[01])\b", text)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    # Pattern 2: DD-MM-YYYY or DD/MM/YYYY
    match = re.search(r"\b(0[1-9]|[12]\d|3[01])[-/.](0[1-9]|1[0-2])[-/.](20\d{2})\b", text)
    if match:
        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"

    # Pattern 3: DD Mon YYYY (e.g., 04 Sep 2026 or 4 September 2026)
    match = re.search(r"\b(0?[1-9]|[12]\d|3[01])\s+([a-zA-Z]{3,9})[,.]?\s+(20\d{2})\b", text)
    if match:
        day = match.group(1).zfill(2)
        mon_str = match.group(2)[:3].lower()
        month = MONTH_MAP.get(mon_str, "01")
        year = match.group(3)
        return f"{year}-{month}-{day}"

    # Pattern 4: DD/MM/YY (short year)
    match = re.search(r"\b(0[1-9]|[12]\d|3[01])[-/.](0[1-9]|1[0-2])[-/.](2[0-9])\b", text)
    if match:
        return f"20{match.group(3)}-{match.group(2)}-{match.group(1)}"

    return today


def extract_merchant(text: str) -> str:
    """
    Extract merchant or store name from receipt header or UPI format.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "Scanned Expense"

    # Check for "Paid to <Name>" or "To: <Name>"
    for line in lines:
        upi_match = re.search(r"\b(?:paid\s+to|merchant|vendor)\s*[:=-]?\s*([A-Za-z0-9\s&'.-]{3,35})", line, re.IGNORECASE)
        if not upi_match:
            upi_match = re.search(r"\bto\s*[:=-]\s*([A-Za-z0-9\s&'.-]{3,35})", line, re.IGNORECASE)
        if upi_match:
            candidate = upi_match.group(1).strip()
            candidate = re.sub(r"(?:completed|successful|upi|ref|transaction|rs|inr|₹).*", "", candidate, flags=re.IGNORECASE).strip()
            if len(candidate) > 2:
                return candidate.title()

    # Look through first 4 lines of receipt (typically store header)
    ignore_words = [
        "tax invoice", "cash receipt", "bill", "invoice", "receipt", "welcome",
        "customer copy", "original", "duplicate", "retail invoice", "date", "time",
        "tel", "gstin", "phone", "order", "table", "cashier", "token"
    ]

    for line in lines[:4]:
        line_clean = re.sub(r"[^\w\s&'-]", "", line).strip()
        lower = line_clean.lower()
        if len(line_clean) >= 3 and not any(ign in lower for ign in ignore_words) and not re.match(r"^[0-9\s:.-]+$", line_clean):
            candidate = line_clean[:35].strip()
            return candidate.title()

    return "Scanned Bill Expense"


def extract_payment_mode(text: str) -> str:
    """
    Detect payment mode used from receipt text.
    """
    lower = text.lower()
    if any(k in lower for k in ["upi", "gpay", "google pay", "phonepe", "paytm", "bhim", "utr", "upi ref"]):
        return "UPI"
    if any(k in lower for k in ["credit card", "visa", "mastercard", "amex", "pos sale", "card ending"]):
        return "Credit Card"
    if any(k in lower for k in ["debit card", "debit"]):
        return "Debit Card"
    if any(k in lower for k in ["net banking", "neft", "rtgs", "imps", "bank transfer"]):
        return "Net Banking"
    if any(k in lower for k in ["cash", "tendered", "change"]):
        return "Cash"

    return "UPI"


def extract_category(text: str, merchant: str) -> str:
    """
    Classify expense category based on merchant name and full text keywords.
    """
    search_space = f"{merchant} {text}".lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", search_space):
                return category

    return "Misc"


def parse_receipt_text(raw_text: str) -> Dict[str, Any]:
    """
    Main entry point: Parse raw OCR text and return structured expense attributes.
    """
    if not raw_text or not raw_text.strip():
        return {
            "title": "New Scanned Expense",
            "amount": 0.0,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "category": "Food",
            "payment_mode": "UPI",
            "raw_text": ""
        }

    clean_text = raw_text.strip()
    amount = extract_amount(clean_text)
    date_str = extract_date(clean_text)
    merchant = extract_merchant(clean_text)
    mode = extract_payment_mode(clean_text)
    category = extract_category(clean_text, merchant)

    return {
        "title": merchant,
        "amount": round(amount, 2),
        "date": date_str,
        "category": category,
        "payment_mode": mode,
        "raw_text": clean_text
    }
