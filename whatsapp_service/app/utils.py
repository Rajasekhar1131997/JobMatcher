import random
import re
import string
from datetime import datetime
from typing import Optional, Tuple, Dict


def generate_confirmation_code() -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    now = datetime.utcnow()
    return f"JOB-{now.strftime('%y%m')}-{suffix}"


def normalize_phone(raw: str) -> Optional[str]:
    digits = re.sub(r"[^\d+]", "", raw or "")
    if len(digits) < 10:
        return None
    if not digits.startswith("+"):
        # Assume country code missing; prepend +1 as a placeholder default
        digits = "+1" + digits
    return digits


def is_yes(text: str) -> bool:
    return text.strip().lower() in {"yes", "y", "confirm", "ok", "okay", "sure"}


def parse_bulk_message(text: str) -> Tuple[dict, list]:
    """
    Extracts fields from a single free-text message.
    Handles semicolons or new lines; tolerates different dash characters.
    """
    required = [
        "title",
        "pay_rate",
        "pay_type",
        "location",
        "shift_times",
        "contact_phone",
        "business_name",
    ]

    label_map = {
        "position": "title",
        "title": "title",
        "role": "title",
        "pay rate": "pay_rate",
        "payrate": "pay_rate",
        "payment type": "pay_type",
        "pay type": "pay_type",
        "payment": "pay_type",
        "location": "location",
        "address": "location",
        "shift timings": "shift_times",
        "shift": "shift_times",
        "shifts": "shift_times",
        "contact phone": "contact_phone",
        "phone": "contact_phone",
        "contact number": "contact_phone",
        "business name": "business_name",
        "business": "business_name",
        "business type": "business_type",
        "minimum qualification": "min_qualification",
        "min qualification": "min_qualification",
        "description": "description",
        "language requirement": "language_requirement",
        "language": "language_requirement",
    }

    found: dict = {}
    # Split on semicolons or newlines
    parts = re.split(r"[;\n]+", text)
    for raw in parts:
        if not raw.strip():
            continue
        # Split on colon or dash variants
        tokens = re.split(r"[:\-–—]\s*", raw, maxsplit=1)
        if len(tokens) != 2:
            continue
        label_raw, value_raw = tokens
        label = label_raw.strip().lower().strip("*").strip()
        value = value_raw.strip()
        if not label or not value:
            continue
        key = label_map.get(label)
        if key:
            found[key] = value

    missing = [f for f in required if f not in found]
    return found, missing


def heuristic_extract(text: str) -> Dict[str, str]:
    """
    Lightweight heuristic extraction for free text:
    - pay_rate: finds $ amounts or digits + /hr/day/week/month
    - pay_type: cash/hourly/salary/monthly keywords
    - contact_phone: phone number or email if no phone
    - shift_times: time ranges like 9AM-5PM or 9am – 5pm
    - location: after 'at <loc>' patterns
    - title: first noun phrase proxy from leading words
    """
    out: Dict[str, str] = {}
    original = text
    # helper to clean trailing punctuation
    def clean(val: str) -> str:
        return val.strip().strip(".,;")
    # Pay rate
    m = re.search(r"(\$?\s?\d+[\.]?\d*)\s*(/|\s?per\s?)?(hour|hr|day|week|month|mo)?", text, re.IGNORECASE)
    if m:
        rate = m.group(1).replace(" ", "")
        unit = m.group(3) or ""
        out["pay_rate"] = f"{rate}/{unit}" if unit else rate
    # Pay type
    m = re.search(r"(cash|salary|salaried|hourly|per\s*hour|per\s*day|per\s*week|per\s*month)", text, re.IGNORECASE)
    if m:
        out["pay_type"] = m.group(1).lower()
    # Contact phone/email
    phone = re.search(r"(\+?\d[\d\-\s]{7,}\d)", text)
    if phone:
        out["contact_phone"] = clean(phone.group(1))
    else:
        email = re.search(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", text, re.IGNORECASE)
        if email:
            out["contact_phone"] = clean(email.group(1))
    # Shift times
    shift = re.search(r"(\d{1,2}\s?(?:am|pm|AM|PM)\s?[-–—]\s?\d{1,2}\s?(?:am|pm|AM|PM))", text)
    if shift:
        out["shift_times"] = shift.group(1)
    # Location
    loc = None
    # cut at keywords to avoid dragging pay rate into location
    loc_match = re.search(r"(?:at|located at|in)\s+([A-Za-z0-9 ,.-]{5,})", text, re.IGNORECASE)
    if loc_match:
        candidate = loc_match.group(1)
        candidate = re.split(r"(?:with|offering|pay rate|payment|from\s+\d)", candidate, maxsplit=1)[0]
        loc = clean(candidate)
    if loc:
        out["location"] = loc
    # Business name / type
    bname = re.search(r"(?:business name|company name|business)\s*(?:is|:)\s*([^.;\n]{3,120})", text, re.IGNORECASE)
    if bname:
        out["business_name"] = clean(bname.group(1 if bname.lastindex == 1 else 2))
    btype = re.search(r"(?:business type|type of business)\s*(?:is|:)\s*([^.;\n]{3,120})", text, re.IGNORECASE)
    if btype:
        out["business_type"] = clean(btype.group(1 if btype.lastindex == 1 else 2))
    # Title: handle "position for/of <role>" and strip lead-in phrases
    title = None
    t1 = re.search(
        r"(?:I have a|I have an|we have a|we have an|hiring a|hiring an|opening for a|opening for an)?\s*position(?:\s+(?:for|of))?\s+([A-Za-z ,'-]{3,80})",
        text,
        re.IGNORECASE,
    )
    if t1:
        title = t1.group(1).strip()
    else:
        sentence = text.strip().split(".")[0]
        words = sentence.split()
        if 2 <= len(words) <= 8:
            title = " ".join(words[:5])
    if title:
        out["title"] = clean(title)
    return out
