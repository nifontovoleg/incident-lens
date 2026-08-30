import json
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.database import get_db
from app.models import Event
from app.schemas import EventCreate, EventCreateResponse, EventResponse

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventCreateResponse, status_code=201)
def create_event(body: EventCreate, db: Session = Depends(get_db)) -> EventCreateResponse:
    start = time.perf_counter()
    try:
        event = Event(
            service=body.service,
            level=body.level,
            message=body.message,
            ts=body.ts,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        result = EventCreateResponse(event_id=event.id)
        log_audit(
            db,
            action="POST /events",
            input_data=body.model_dump(),
            output_data=result.model_dump(),
            status="ok",
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        return result
    except Exception as exc:
        log_audit(
            db,
            action="POST /events",
            input_data=body.model_dump() if hasattr(body, "model_dump") else {},
            output_data=None,
            status="error",
            error=str(exc),
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        raise


@router.get("", response_model=list[EventResponse])
def list_events(
    service: str | None = Query(None),
    level: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[EventResponse]:
    start = time.perf_counter()
    q = db.query(Event).order_by(Event.created_at.desc())
    if service:
        q = q.filter(Event.service == service)
    if level:
        q = q.filter(Event.level == level)
    events = q.all()
    result = [
        EventResponse(
            event_id=e.id,
            created_at=e.created_at,
            service=e.service,
            level=e.level,
            message=e.message,
            ts=e.ts,
        )
        for e in events
    ]
    log_audit(
        db,
        action="GET /events",
        input_data={"service": service, "level": level},
        output_data={"count": len(result)},
        status="ok",
        duration_ms=int((time.perf_counter() - start) * 1000),
    )
    return result


@router.get("/services", response_model=list[str])
def list_services(db: Session = Depends(get_db)) -> list[str]:
    rows = db.query(Event.service).distinct().all()
    return sorted(r[0] for r in rows)
