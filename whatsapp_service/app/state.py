import time
from typing import Dict, List, Optional
from .models import SessionState, FormField


class SessionStore:
    """In-memory session store; replace with Redis in production."""

    class Session:
        def __init__(self, chat_id: str):
            self.chat_id = chat_id
            self.state = SessionState.collecting
            self.started_at = time.time()
            self.collected_payload: Dict[str, str] = {}
            self.form = _build_form()
            self.form_order: List[str] = [k for k in self.form.keys()]
            self._current_index = 0
            self.bulk_expected = True  # expect a single message with all fields by default

        @property
        def current_field(self) -> Optional[str]:
            if self._current_index < len(self.form_order):
                return self.form_order[self._current_index]
            return None

        def current_prompt(self) -> str:
            field = self.current_field
            if field is None:
                return "All fields collected."
            item = self.form[field]
            return f"{item['prompt']}"

        def advance(self) -> None:
            if self._current_index + 1 < len(self.form_order):
                self._current_index += 1
                self.state = SessionState.collecting
            else:
                self.state = SessionState.review

        def edit_field(self, field: str) -> None:
            if field in self.form:
                self._current_index = self.form_order.index(field)
                self.state = SessionState.collecting

        def bulk_prompt(self) -> str:
            lines = [
                "Hello, Welcome to the Job Posting Service!",
                "Please send all job details in one message, by following this template:",
                "",
                "Position *: (e.g., Cashier, Server, Delivery Driver)",
                "Pay rate *: (e.g., $18/hr or $1000/month)",
                "Payment type *: (e.g., salary, cash, cheques)",
                "Location *: (e.g., address or map pin)",
                "Shift timings *: (e.g., Mon-Fri 4pm-10pm)",
                "Contact phone *: (e.g., phone number)",
                "Business name *: (e.g., Name of the Business)",
                "Business type *: (e.g., Restaurant, Retail, etc.)",
                "Minimum qualification: (optional)",
                "Description: (optional)",
                "Language requirement: (e.g., English, Spanish) (optional)",
                "",
                "Fields with \"*\" are mandatory.",
                "You can separate fields with semicolons or new lines. You may also attach photos in the same message.",
            ]
            return "\n".join(lines)

    def __init__(self):
        self.sessions: Dict[str, SessionStore.Session] = {}
        self.ttl_seconds = 60 * 30  # 30 minutes

    def start(self, chat_id: str) -> "Session":
        session = SessionStore.Session(chat_id)
        self.sessions[chat_id] = session
        return session

    def get(self, chat_id: str) -> Optional["Session"]:
        session = self.sessions.get(chat_id)
        if session and time.time() - session.started_at > self.ttl_seconds:
            self.end(chat_id)
            return None
        return session

    def end(self, chat_id: str) -> None:
        self.sessions.pop(chat_id, None)


def _build_form() -> Dict[str, Dict[str, str]]:
    return {
        FormField.title: {
            "prompt": "Position/title for the job?",
        },
        FormField.pay_rate: {
            "prompt": "Pay rate (e.g., 18/hr or 150/day)?",
        },
        FormField.pay_type: {
            "prompt": "Payment type (hourly, salary, cash)?",
        },
        FormField.location: {
            "prompt": "Location/address or map pin?",
        },
        FormField.shift_times: {
            "prompt": "Shift timings and days (e.g., Mon-Fri 4pm-10pm)?",
        },
        FormField.contact_phone: {
            "prompt": "Contact phone to reach you?",
        },
        FormField.business_name: {
            "prompt": "Business name?",
        },
        FormField.business_type: {
            "prompt": "Business type (restaurant, retail, etc.)?",
        },
        FormField.min_qualification: {
            "prompt": "Minimum qualification (optional)?",
        },
        FormField.description: {
            "prompt": "Short description (optional)?",
        },
        FormField.language_requirement: {
            "prompt": "Language requirement (optional)?",
        },
    }
