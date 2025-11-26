Whatsapp Integration Service (MVP)
==================================

FastAPI microservice that runs the WhatsApp “Hi → structured form → confirmation code” flow for business job postings. It maintains a simple session state per chat, validates fields, and emits a structured job payload (stubbed publish hook for now).

Quickstart
----------
- Prereqs: Python 3.10+, `pip install -r requirements.txt`.
- Run locally: `uvicorn app.main:app --reload --port 8000`.
- Test webhook (simulate WhatsApp/Twilio payload):
  ```
  curl -X POST http://localhost:8000/webhook \
    -H "Content-Type: application/json" \
    -d '{"from":"+15551234567","text":"Hi"}'
  ```
  Then send all fields in one message, e.g.:
  ```
  curl -X POST http://localhost:8000/webhook \
    -H "Content-Type: application/json" \
    -d '{"from":"+15551234567","text":"Position: Cashier; Pay rate: 18/hr; Payment type: hourly; Location: 123 Main St; Shift timings: Mon-Fri 4-10pm; Contact phone: +15551234567; Business name: Joes Diner; Business type: Restaurant; Minimum qualification: HS diploma; Description: Evening shift; Language requirement: English"}'
  ```

Key Endpoints
-------------
- `POST /webhook`: receives inbound WhatsApp-style message payload, advances the session state machine, and returns the next message to send.
- `GET /health`: liveness probe.
- `POST /twilio/webhook`: Twilio WhatsApp webhook endpoint. Accepts Twilio form-encoded payloads, validates optional X-Twilio-Signature, and responds with TwiML.
- `GET /jobs`: returns in-memory jobs captured from confirmations (for local/demo feed).

Twilio WhatsApp Setup
---------------------
- Configure your Twilio WhatsApp Sandbox/number webhook to: `https://<your-host>/twilio/webhook`.
- Set `TWILIO_AUTH_TOKEN` in environment (or `.env`) to enable signature verification. If not set, validation is skipped.
- Local testing: run the app, expose with ngrok (`ngrok http 8000`), and point Twilio webhook to the ngrok URL + `/twilio/webhook`.

Notes
-----
- Session store is in-memory for MVP; swap with Redis for production.
- Confirmation codes follow `JOB-YYMM-XXXXX` and are stored with the job payload.

Publishing to Job Service
-------------------------
- Set `JOB_SERVICE_URL` to your Job Service endpoint (e.g., `https://api.example.com/jobs`).
- Optional bearer auth: set `JOB_SERVICE_TOKEN` (adds `Authorization: Bearer <token>`).
- Optional tuning: `JOB_SERVICE_TIMEOUT` (default 5.0 seconds), `JOB_SERVICE_RETRIES` (default 2).
- On YES confirmation, the service attempts to POST the job payload; on failure it keeps the session in review and asks to retry YES.
- Regardless of external publish, confirmed jobs are also stored in-memory and exposed at `GET /jobs` for the sample frontend.

Free-text Parsing (LLM Fallback: OpenAI)
----------------------------------------
- If required fields are missing from the incoming free-text message, the service attempts to extract them via OpenAI Chat Completions.
- Set `OPENAI_API_KEY` to enable. Optional: `OPENAI_MODEL` (default `gpt-4o-mini`), `OPENAI_BASE_URL` to override the endpoint.
- If the LLM is disabled or extraction fails, the user is prompted to resend using the template.
--