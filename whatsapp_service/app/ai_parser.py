import json
import os
import re
from typing import Dict

import httpx


def _clean_value(val: str) -> str:
    v = (val or "").strip().strip(".,;")
    v = re.sub(r"^(i have a|i have an|we have a|we have an|hiring a|hiring an|opening for a|opening for an)\s+", "", v, flags=re.IGNORECASE)
    return v


def llm_parse_free_text(text: str) -> Dict[str, str]:
    """
    Attempts to extract job fields from unstructured text using OpenAI Chat Completions.
    Returns a dict with any fields found; missing keys are omitted.
    Requires OPENAI_API_KEY in env. If unavailable or on error, returns {}.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    endpoint = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions")
    if not api_key:
        return {}

    examples = """
Input:
I have a Front desk student assistant position at California State University, Sacramento with offering pay rate of $18 per hour and the payment will be biweekly deposited into their registered account. Should be able to work from 9AM - 5PM from Monday to Friday. You can reach out or send your resumes to rajakolagotla@gmail.com. Candidates should be able to communicate in English and Spanish and should be able to well receive the customers coming to the office. Type of business is education and business name is Social welfare office at California State University-Sacramento.
Output:
{"title":"Front desk student assistant","pay_rate":"$18/hour","pay_type":"hourly","location":"California State University, Sacramento","shift_times":"9AM - 5PM Monday to Friday","contact_phone":"rajakolagotla@gmail.com","business_name":"Social welfare office at California State University-Sacramento","business_type":"education","min_qualification":"","description":"Candidates should be able to communicate in English and Spanish and should be able to well receive the customers coming to the office.","language_requirement":"English, Spanish"}

Input:
Hiring a barista. $20/hr. Location: 123 Market St, SF. Shifts: Sat-Sun 7am-1pm. Contact: +15551234567. Business: Moonlight Cafe, type restaurant. Need latte art.
Output:
{"title":"barista","pay_rate":"$20/hr","pay_type":"hourly","location":"123 Market St, SF","shift_times":"Sat-Sun 7am-1pm","contact_phone":"+15551234567","business_name":"Moonlight Cafe","business_type":"restaurant","min_qualification":"","description":"Need latte art.","language_requirement":""}
"""

    system = (
        "You extract concise structured job data from free text.\n"
        "Return a strict JSON object with keys: "
        "title, pay_rate, pay_type, location, shift_times, contact_phone, business_name, "
        "business_type, min_qualification, description, language_requirement. "
        "Use empty strings for missing fields. Strip lead-in phrases like 'I have a', "
        "'We have an', 'Hiring a' from title/business. Respond with JSON only."
    )
    user = f"{examples}\nMessage:\n{text}"

    try:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": 300,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        resp = httpx.post(endpoint, headers=headers, json=payload, timeout=10.0)
        if resp.status_code != 200:
            return {}
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            cleaned = {}
            for k, v in parsed.items():
                cleaned[k] = _clean_value(v) if isinstance(v, str) else ""
            return cleaned
    except Exception:
        return {}
    return {}
