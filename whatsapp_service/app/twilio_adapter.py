import base64
import hashlib
import hmac
from typing import Dict, List
from xml.sax.saxutils import escape
from fastapi import HTTPException, Request
from .models import InboundMessage


def parse_twilio_form(form: Dict[str, str]) -> InboundMessage:
    """
    Converts Twilio WhatsApp form-encoded webhook into an InboundMessage.
    Expects fields: From, Body, NumMedia, MediaUrl{N}
    """
    from_number = form.get("From") or form.get("FromFull") or ""
    text = form.get("Body", "")
    num_media = int(form.get("NumMedia", "0") or 0)
    media_urls: List[str] = []
    for i in range(num_media):
        url = form.get(f"MediaUrl{i}")
        if url:
            media_urls.append(url)
    return InboundMessage(from_number=from_number, text=text, media_urls=media_urls)


def twiml_response(message: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{escape(message)}</Message></Response>'


def validate_twilio_request(auth_token: str, request: Request, form: Dict[str, str]) -> None:
    """
    Validates X-Twilio-Signature header using the provided auth token.
    Raises 403 on mismatch. If header missing, skips validation.
    """
    signature = request.headers.get("X-Twilio-Signature")
    if not signature:
        return
    url = str(request.url)
    expected = _compute_signature(auth_token, url, form)
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")


def _compute_signature(auth_token: str, url: str, params: Dict[str, str]) -> str:
    """
    Implements Twilio request validation:
    signature = base64encode(HMAC_SHA1(auth_token, url + concat(sorted_param_key + value)))
    """
    s = url
    for key in sorted(params.keys()):
        s += key + params[key]
    digest = hmac.new(auth_token.encode("utf-8"), s.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("utf-8")
