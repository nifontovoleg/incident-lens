import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    service: Mapped[str] = mapped_column(String(128), index=True)
    level: Mapped[str] = mapped_column(String(16), index=True)
    message: Mapped[str] = mapped_column(Text)
    ts: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    title: Mapped[str] = mapped_column(String(256))

    events: Mapped[list["Event"]] = relationship(
        secondary="incident_events",
        backref="incidents",
    )
    diagnoses: Mapped[list["Diagnosis"]] = relationship(back_populates="incident")


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    incident_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("incidents.id"), primary_key=True
    )
    event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("events.id"), primary_key=True
    )


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    incident_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("incidents.id"), nullable=True
    )
    diagnosis_json: Mapped[str] = mapped_column(Text)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(String(64), nullable=True)

    incident: Mapped["Incident | None"] = relationship(back_populates="diagnoses")


class AuditRun(Base):
    __tablename__ = "audit_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    action: Mapped[str] = mapped_column(String(64), index=True)
    input: Mapped[str] = mapped_column(Text)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(default=0)
