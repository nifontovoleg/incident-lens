from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import settings
from app.database import init_db
from app.routers import ai, audit, events, incidents

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_title, lifespan=lifespan)

app.include_router(events.router)
app.include_router(incidents.router)
app.include_router(ai.router)
app.include_router(audit.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    from app.database import SessionLocal
    from app.audit import log_audit

    db = SessionLocal()
    try:
        body = None
        try:
            body = await request.json()
        except Exception:
            body = {"raw": "unparseable"}
        log_audit(
            db,
            action=f"{request.method} {request.url.path}",
            input_data=body or {"errors": exc.errors()},
            output_data=None,
            status="error",
            error="VALIDATION_ERROR",
            duration_ms=0,
        )
    finally:
        db.close()
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
