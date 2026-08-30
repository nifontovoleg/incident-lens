import json
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditRun


def log_audit(
    db: Session,
    action: str,
    input_data: Any,
    output_data: Any | None,
    status: str,
    error: str | None = None,
    duration_ms: int = 0,
) -> None:
    record = AuditRun(
        action=action,
        input=json.dumps(input_data, ensure_ascii=False, default=str),
        output=(
            json.dumps(output_data, ensure_ascii=False, default=str)
            if output_data is not None
            else None
        ),
        status=status,
        error=error,
        duration_ms=duration_ms,
    )
    db.add(record)
    db.commit()


def audited(action: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            db: Session | None = kwargs.get("db")
            if db is None:
                for arg in args:
                    if isinstance(arg, Session):
                        db = arg
                        break
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration = int((time.perf_counter() - start) * 1000)
                if db is not None:
                    log_audit(
                        db,
                        action=action,
                        input_data=kwargs.get("body") or kwargs,
                        output_data=result if isinstance(result, dict) else None,
                        status="ok",
                        duration_ms=duration,
                    )
                return result
            except Exception as exc:
                duration = int((time.perf_counter() - start) * 1000)
                if db is not None:
                    log_audit(
                        db,
                        action=action,
                        input_data=kwargs.get("body") or kwargs,
                        output_data=None,
                        status="error",
                        error=str(exc),
                        duration_ms=duration,
                    )
                raise

        return wrapper

    return decorator
