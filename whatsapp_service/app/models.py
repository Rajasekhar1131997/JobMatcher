from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SessionState(str, Enum):
    collecting = "collecting"
    review = "review"
    confirmed = "confirmed"


class FormField:
    title = "title"
    pay_rate = "pay_rate"
    pay_type = "pay_type"
    location = "location"
    shift_times = "shift_times"
    contact_phone = "contact_phone"
    business_name = "business_name"
    business_type = "business_type"
    min_qualification = "min_qualification"
    description = "description"
    language_requirement = "language_requirement"


class InboundMessage(BaseModel):
    from_number: str = Field(..., alias="from")
    text: Optional[str] = None
    media_urls: Optional[List[str]] = None

    class Config:
        allow_population_by_field_name = True

    @property
    def text_lower(self) -> str:
        return (self.text or "").strip().lower()


class OutboundMessage(BaseModel):
    to: str
    message: str
    state: SessionState
    collected: Dict[str, Any]


class JobPayload(BaseModel):
    confirmation_code: str
    source_channel: str = "wa"
    chat_id: str
    title: str
    pay_rate: str
    pay_type: str
    location: str
    shift_times: str
    contact_phone: str
    business_name: str
    business_type: Optional[str] = None
    min_qualification: Optional[str] = None
    description: Optional[str] = None
    language_requirement: Optional[str] = None
    images: List[str] = Field(default_factory=list)
