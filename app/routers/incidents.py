import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.database import get_db
from app.models import Event, Incident, IncidentEvent
from app.schemas import IncidentCreate, IncidentCreateResponse, IncidentResponse

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.post("", response_model=IncidentCreateResponse, status_code=201)
def create_incident(
    body: IncidentCreate, db: Session = Depends(get_db)
) -> IncidentCreateResponse:
    start = time.perf_counter()
    events = db.query(Event).filter(Event.id.in_(body.event_ids)).all()
    found_ids = {e.id for e in events}
    missing = set(body.event_ids) - found_ids
    if missing:
        log_audit(
            db,
            action="POST /incidents",
            input_data=body.model_dump(),
            output_data=None,
            status="error",
            error=f"Events not found: {sorted(missing)}",
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        raise HTTPException(
            status_code=404,
            detail=f"Events not found: {sorted(missing)}",
        )

    incident = Incident(title=body.title)
    db.add(incident)
    db.flush()
    for eid in body.event_ids:
        db.add(IncidentEvent(incident_id=incident.id, event_id=eid))
    db.commit()
    db.refresh(incident)
    result = IncidentCreateResponse(incident_id=incident.id)
    log_audit(
        db,
        action="POST /incidents",
        input_data=body.model_dump(),
        output_data=result.model_dump(),
        status="ok",
        duration_ms=int((time.perf_counter() - start) * 1000),
    )
    return result


@router.get("", response_model=list[IncidentResponse])
def list_incidents(db: Session = Depends(get_db)) -> list[IncidentResponse]:
    incidents = (
        db.query(Incident).order_by(Incident.created_at.desc()).limit(20).all()
    )
    result = []
    for inc in incidents:
        event_ids = [
            ie.event_id
            for ie in db.query(IncidentEvent)
            .filter(IncidentEvent.incident_id == inc.id)
            .all()
        ]
        result.append(
            IncidentResponse(
                incident_id=inc.id,
                created_at=inc.created_at,
                title=inc.title,
                event_ids=event_ids,
            )
        )
    return result


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: str, db: Session = Depends(get_db)) -> IncidentResponse:
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    event_ids = [
        ie.event_id
        for ie in db.query(IncidentEvent)
        .filter(IncidentEvent.incident_id == inc.id)
        .all()
    ]
    return IncidentResponse(
        incident_id=inc.id,
        created_at=inc.created_at,
        title=inc.title,
        event_ids=event_ids,
    )
