from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class EventCreate(BaseModel):
    service: str = Field(min_length=1)
    level: Literal["info", "warning", "error"]
    message: str = Field(min_length=1)
    ts: str | None = None

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be empty")
        return v


class EventResponse(BaseModel):
    event_id: str
    created_at: datetime
    service: str
    level: str
    message: str
    ts: str | None

    model_config = {"from_attributes": True}


class EventCreateResponse(BaseModel):
    status: Literal["ok"] = "ok"
    event_id: str


class IncidentCreate(BaseModel):
    title: str = Field(min_length=1)
    event_ids: list[str] = Field(min_length=1)


class IncidentCreateResponse(BaseModel):
    status: Literal["ok"] = "ok"
    incident_id: str


class IncidentResponse(BaseModel):
    incident_id: str
    created_at: datetime
    title: str
    event_ids: list[str]


class DiagnoseRequest(BaseModel):
    title: str = Field(min_length=1)
    messages: list[str] = Field(min_length=1)
    incident_id: str | None = None


class DiagnoseResponse(BaseModel):
    root_cause_hypothesis: str
    confidence: Literal["high", "medium", "low"]
    next_steps: list[str]
    needs_review: bool


class AuditRunResponse(BaseModel):
    id: str
    created_at: datetime
    action: str
    input: str
    output: str | None
    status: str
    error: str | None
    duration_ms: int

    model_config = {"from_attributes": True}
