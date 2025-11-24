import os
import asyncio
import logging
from urllib.parse import parse_qs
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from dotenv import load_dotenv
from typing import Dict, Optional
import httpx
from .storage import store
from .models import (
    InboundMessage,
    OutboundMessage,
    SessionState,
    JobPayload,
    FormField,
)
from .state import SessionStore
from .utils import (
    generate_confirmation_code,
    normalize_phone,
    is_yes,
    parse_bulk_message,
    heuristic_extract,
)
from .twilio_adapter import (
    parse_twilio_form,
    twiml_response,
    validate_twilio_request,
)
from .ai_parser import llm_parse_free_text
from .db import Database

load_dotenv()
app = FastAPI(title="WhatsApp Integration Service", version="0.1.0")
logger = logging.getLogger("jobmatcher")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
sessions = SessionStore()
JOB_SERVICE_URL = os.getenv("JOB_SERVICE_URL")
JOB_SERVICE_TOKEN = os.getenv("JOB_SERVICE_TOKEN")
JOB_SERVICE_TIMEOUT = float(os.getenv("JOB_SERVICE_TIMEOUT", "5.0"))
JOB_SERVICE_RETRIES = int(os.getenv("JOB_SERVICE_RETRIES", "2"))
PG_DSN = os.getenv("PG_DSN")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
db: Optional[Database] = None


@app.on_event("startup")
async def startup_event():
    global db
    if PG_DSN:
        db = Database(PG_DSN)
        try:
            await db.connect()
            logger.info("Connected to Postgres")
        except Exception as exc:
            logger.error(f"Failed to connect to Postgres: {exc}")
            db = None


@app.on_event("shutdown")
async def shutdown_event():
    if db:
        await db.close()


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "db": bool(db)}

@app.get("/jobs")
async def list_jobs(source: Optional[str] = None):
    """Return jobs from Postgres if configured, otherwise in-memory."""
    if db:
        return await db.list_jobs(source)
    return store.all(source)


@app.post("/webhook", response_model=OutboundMessage)
async def webhook(msg: InboundMessage):
    outbound = await _handle_message(msg)
    return JSONResponse(status_code=200, content=outbound.dict())


@app.post("/twilio/webhook")
async def twilio_webhook(request: Request):
    # Parse urlencoded form manually to avoid python-multipart dependency
    body = await request.body()
    form_dict = {k: v[0] if isinstance(v, list) else v for k, v in parse_qs(body.decode()).items()}

    # Optional: validate Twilio signature if auth token is configured
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    if auth_token:
        validate_twilio_request(auth_token, request, form_dict)

    inbound = parse_twilio_form(form_dict)
    outbound = await _handle_message(inbound)
    xml = twiml_response(outbound.message)
    return Response(content=xml, media_type="application/xml")


async def _handle_message(msg: InboundMessage) -> OutboundMessage:
    chat_id = msg.from_number
    session = sessions.get(chat_id)

    # Start or restart session on hi/restart
    if session is None or msg.text_lower in ("hi", "hello", "restart", "start"):
        session = sessions.start(chat_id)
        prompt = session.bulk_prompt()
        return OutboundMessage(
            to=chat_id,
            message=prompt,
            state=session.state,
            collected=session.collected_payload,
        )

    # Handle media-only message (attach images and advance)
    if msg.media_urls and not msg.text:
        session.collected_payload.setdefault("images", []).extend(msg.media_urls)
        return _advance_or_confirm(session, chat_id)

    # Handle confirm/yes after summary
    if session.state == SessionState.review and is_yes(msg.text_lower):
        payload = _build_job_payload(session, chat_id)
        ok, publish_msg = await publish_job(payload)
        if ok:
            code = payload.confirmation_code
            store.add(payload)  # also keep locally for demo feed
            sessions.end(chat_id)
            link = f"{FRONTEND_URL}?ref={code}"
            return OutboundMessage(
                to=chat_id,
                message=f"Thanks! Your job is published with confirmation code {code}.\nView it here: {link}",
                state=SessionState.confirmed,
                collected=payload.dict(),
            )
        # Keep session alive on failure so they can retry YES
        session.state = SessionState.review
        return OutboundMessage(
            to=chat_id,
            message=f"Could not publish right now: {publish_msg}. Please reply YES to retry.",
            state=session.state,
            collected=payload.dict(),
        )

    # Handle simple edit command
    if msg.text_lower.startswith("edit"):
        parts = msg.text_lower.split()
        if len(parts) >= 2:
            field = parts[1]
            if field in session.form_order:
                session.edit_field(field)
                return OutboundMessage(
                    to=chat_id,
                    message=f"Okay, update {field}:\n{session.form[field]['prompt']}",
                    state=session.state,
                    collected=session.collected_payload,
                )

    # Bulk single-message collection path
    if session.bulk_expected and session.state == SessionState.collecting and msg.text:
        parsed, missing = parse_bulk_message(msg.text)
        if "contact_phone" in parsed:
            phone = normalize_phone(parsed["contact_phone"])
            if phone is None:
                missing = list(set(missing + ["contact_phone"]))
            else:
                parsed["contact_phone"] = phone
        if msg.media_urls:
            parsed.setdefault("images", []).extend(msg.media_urls)

        # Heuristic extraction
        if missing:
            heur = heuristic_extract(msg.text)
            for k, v in heur.items():
                if v and k not in parsed:
                    parsed[k] = v
            if "contact_phone" in parsed:
                phone = normalize_phone(parsed["contact_phone"])
                if phone is None:
                    missing = list(set(missing + ["contact_phone"]))
                else:
                    parsed["contact_phone"] = phone
            missing = [f for f in ["title","pay_rate","pay_type","location","shift_times","contact_phone","business_name"] if f not in parsed or not parsed.get(f)]

        # LLM extraction
        if missing:
            llm = llm_parse_free_text(msg.text)
            if llm:
                for k, v in llm.items():
                    if v and k not in parsed:
                        parsed[k] = v
                if "contact_phone" in parsed:
                    phone = normalize_phone(parsed["contact_phone"])
                    if phone is None:
                        if "contact_phone" in parsed:
                            parsed.pop("contact_phone", None)
                    else:
                        parsed["contact_phone"] = phone
            missing = [f for f in ["title","pay_rate","pay_type","location","shift_times","contact_phone","business_name"] if f not in parsed or not parsed.get(f)]

        if missing:
            missing_list = ", ".join(missing)
            return OutboundMessage(
                to=chat_id,
                message=f"I couldn't find these fields: {missing_list}. Please resend all details in one message using the template.\n\n{session.bulk_prompt()}",
                state=session.state,
                collected=session.collected_payload,
            )
        session.collected_payload = parsed
        session.state = SessionState.review
        summary = _build_summary(session.collected_payload)
        return OutboundMessage(
            to=chat_id,
            message=summary,
            state=session.state,
            collected=session.collected_payload,
        )

    # Collect answer for current field (multi-turn fallback)
    current_field = session.current_field
    if current_field is None:
        # Session expired or inconsistent; restart
        sessions.end(chat_id)
        raise HTTPException(status_code=400, detail="Session expired, please send 'Hi' to restart.")

    # Basic validation
    if current_field == FormField.contact_phone:
        phone = normalize_phone(msg.text)
        if phone is None:
            return _validation_error(chat_id, session, "Please provide a valid phone number (e.g., +15551234567).")
        session.collected_payload[current_field] = phone
    else:
        session.collected_payload[current_field] = msg.text.strip()

    return _advance_or_confirm(session, chat_id)


def _advance_or_confirm(session: SessionStore.Session, chat_id: str) -> OutboundMessage:
    session.advance()
    if session.state == SessionState.review:
        summary = _build_summary(session.collected_payload)
        return OutboundMessage(
            to=chat_id,
            message=summary,
            state=session.state,
            collected=session.collected_payload,
        )
    prompt = session.current_prompt()
    return OutboundMessage(
        to=chat_id,
        message=prompt,
        state=session.state,
        collected=session.collected_payload,
    )


def _build_summary(collected: Dict[str, str]) -> str:
    lines = [
        "Please review your job post:",
        f"Position: {collected.get(FormField.title, '—')}",
        f"Pay rate/type: {collected.get(FormField.pay_rate, '—')} ({collected.get(FormField.pay_type, '—')})",
        f"Location: {collected.get(FormField.location, '—')}",
        f"Shift timings: {collected.get(FormField.shift_times, '—')}",
        f"Contact phone: {collected.get(FormField.contact_phone, '—')}",
        f"Business name/type: {collected.get(FormField.business_name, '—')}",
        f"Minimum qualification: {collected.get(FormField.min_qualification, '—')}",
        f"Description: {collected.get(FormField.description, '—')}",
        f"Language requirement: {collected.get(FormField.language_requirement, '—')}",
        f"Images: {len(collected.get('images', []))} attached",
        "",
        "Reply YES to confirm, or 'edit <field>' to change a value.",
    ]
    return "\n".join(lines)


def _build_job_payload(session: SessionStore.Session, chat_id: str) -> JobPayload:
    confirmation_code = generate_confirmation_code()
    payload = JobPayload(
        confirmation_code=confirmation_code,
        source_channel="wa",
        chat_id=chat_id,
        **session.collected_payload,
    )
    return payload


async def publish_job(payload: JobPayload) -> (bool, str):
    """
    POST job payload to Job Service.
    Returns (ok, message).
    """
    if not JOB_SERVICE_URL:
        # No external job service configured; treat as success for local/demo storage.
        if db:
            await db.add_job(payload.dict())
        return True, "local-only"
    headers = {"Content-Type": "application/json"}
    if JOB_SERVICE_TOKEN:
        headers["Authorization"] = f"Bearer {JOB_SERVICE_TOKEN}"
    body = payload.dict()
    attempt = 0
    last_error: Optional[str] = None
    while attempt <= JOB_SERVICE_RETRIES:
        attempt += 1
        try:
            resp = httpx.post(
                JOB_SERVICE_URL,
                json=body,
                headers=headers,
                timeout=JOB_SERVICE_TIMEOUT,
            )
            if resp.status_code // 100 == 2:
                if db:
                    await db.add_job(payload.dict())
                return True, "published"
            last_error = f"{resp.status_code} {resp.text}"
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
    return False, last_error or "unknown error"


def _validation_error(chat_id: str, session: SessionStore.Session, hint: str) -> OutboundMessage:
    return OutboundMessage(
        to=chat_id,
        message=f"{hint}\n{session.form[session.current_field]['prompt']}",
        state=session.state,
        collected=session.collected_payload,
    )
