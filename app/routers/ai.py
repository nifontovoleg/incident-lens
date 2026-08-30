import json
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.database import get_db
from app.models import Diagnosis
from app.schemas import DiagnoseRequest, DiagnoseResponse
from app.services.diagnosis import diagnose

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/diagnose", response_model=DiagnoseResponse)
def run_diagnosis(
    body: DiagnoseRequest, db: Session = Depends(get_db)
) -> DiagnoseResponse:
    start = time.perf_counter()
    try:
        result = diagnose(body.title, body.messages)
        diagnosis_json = result.model_dump_json()
        needs_review = result.needs_review
        error_field = None
    except Exception as exc:
        result = DiagnoseResponse(
            root_cause_hypothesis="Не удалось выполнить диагностику.",
            confidence="low",
            next_steps=[
                "Собрать уточнения: логи и метрики за период инцидента.",
                "Повторить диагностику после добавления событий.",
            ],
            needs_review=True,
        )
        diagnosis_json = json.dumps({"error": str(exc)})
        needs_review = True
        error_field = "INVALID_JSON"

    record = Diagnosis(
        incident_id=body.incident_id,
        diagnosis_json=diagnosis_json if error_field is None else diagnosis_json,
        needs_review=needs_review,
        error=error_field,
    )
    db.add(record)
    db.commit()

    log_audit(
        db,
        action="POST /ai/diagnose",
        input_data=body.model_dump(),
        output_data=result.model_dump(),
        status="ok" if error_field is None else "error",
        error=error_field,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )
    return result


@router.get("/diagnoses/latest", response_model=DiagnoseResponse | None)
def latest_diagnosis(db: Session = Depends(get_db)) -> DiagnoseResponse | None:
    record = db.query(Diagnosis).order_by(Diagnosis.created_at.desc()).first()
    if not record:
        return None
    try:
        data = json.loads(record.diagnosis_json)
        return DiagnoseResponse(**data)
    except (json.JSONDecodeError, ValidationError):
        return DiagnoseResponse(
            root_cause_hypothesis="Ошибка формата ответа диагностики.",
            confidence="low",
            next_steps=[
                "Собрать уточнения: логи и метрики.",
                "Повторить диагностику.",
            ],
            needs_review=True,
        )


@router.get("/diagnoses/{diagnosis_id}")
def get_diagnosis(diagnosis_id: str, db: Session = Depends(get_db)) -> dict:
    record = db.query(Diagnosis).filter(Diagnosis.id == diagnosis_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Diagnosis not found")
    try:
        data = json.loads(record.diagnosis_json)
    except json.JSONDecodeError:
        data = {}
    return {
        "id": record.id,
        "created_at": record.created_at.isoformat(),
        "incident_id": record.incident_id,
        "needs_review": record.needs_review,
        "error": record.error,
        **data,
    }
