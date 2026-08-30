import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditRun
from app.schemas import AuditRunResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/runs", response_model=list[AuditRunResponse])
def list_audit_runs(
    limit: int = 50, db: Session = Depends(get_db)
) -> list[AuditRunResponse]:
    runs = (
        db.query(AuditRun).order_by(AuditRun.created_at.desc()).limit(limit).all()
    )
    return [AuditRunResponse.model_validate(r) for r in runs]
