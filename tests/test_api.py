import json
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as db_module
from app.database import Base, get_db
from app.main import app
from app.services.diagnosis import diagnose

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    original_session_local = db_module.SessionLocal
    db_module.SessionLocal = TestingSessionLocal
    with TestClient(app) as c:
        yield c
    db_module.SessionLocal = original_session_local
    app.dependency_overrides.clear()


def _create_event(client, **kwargs):
    payload = {
        "service": "demo",
        "level": "info",
        "message": "test event",
        "ts": None,
        **kwargs,
    }
    return client.post("/events", json=payload)


class TestEvents:
    def test_add_and_list_events(self, client):
        r = _create_event(client, message="Запуск сервиса")
        assert r.status_code == 201
        event_id = r.json()["event_id"]

        r2 = client.get("/events")
        assert r2.status_code == 200
        events = r2.json()
        assert any(e["event_id"] == event_id for e in events)

    def test_filter_by_service_and_level(self, client):
        _create_event(client, service="alpha", level="error", message="err alpha")
        _create_event(client, service="beta", level="info", message="info beta")

        r = client.get("/events?service=alpha&level=error")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["service"] == "alpha"

    def test_invalid_event_validation(self, client):
        r = client.post(
            "/events",
            json={"service": "demo", "level": "invalid", "message": "", "ts": None},
        )
        assert r.status_code == 422

        audits = client.get("/audit/runs").json()
        assert any(a["status"] == "error" for a in audits)


class TestIncidents:
    def test_create_incident_from_events(self, client):
        ids = []
        for msg in ["error one", "error two"]:
            r = _create_event(client, level="error", message=msg)
            ids.append(r.json()["event_id"])

        r = client.post(
            "/incidents",
            json={"title": "DB problems", "event_ids": ids},
        )
        assert r.status_code == 201
        assert "incident_id" in r.json()

    def test_create_incident_missing_events(self, client):
        r = client.post(
            "/incidents",
            json={"title": "Ghost", "event_ids": ["nonexistent-id"]},
        )
        assert r.status_code == 404


class TestDiagnosis:
    def test_diagnose_db_locked_high_confidence(self, client):
        r = client.post(
            "/ai/diagnose",
            json={
                "title": "DB issue",
                "messages": ["DB locked: unable to acquire write lock"],
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["confidence"] == "high"
        assert data["needs_review"] is False
        assert "root_cause_hypothesis" in data
        assert len(data["next_steps"]) >= 1

    def test_diagnose_needs_review_low_confidence(self, client):
        r = client.post(
            "/ai/diagnose",
            json={
                "title": "Что-то не так",
                "messages": ["ошибка", "сбой"],
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["confidence"] == "low"
        assert data["needs_review"] is True
        assert data["next_steps"][0].lower().startswith("собрать")

    def test_diagnosis_saved_to_db(self, client):
        r = client.post(
            "/ai/diagnose",
            json={
                "title": "Timeout",
                "messages": ["Timeout to external service after 30s"],
                "incident_id": None,
            },
        )
        assert r.status_code == 200
        latest = client.get("/ai/diagnoses/latest")
        assert latest.status_code == 200
        assert latest.json()["confidence"] == "high"


class TestAudit:
    def test_audit_runs_recorded(self, client):
        _create_event(client, message="audit test")
        audits = client.get("/audit/runs").json()
        assert len(audits) >= 1
        assert any(a["action"] == "POST /events" for a in audits)


class TestDiagnosisService:
    def test_vague_messages_need_review(self):
        result = diagnose("Проблема", ["ошибка", "сбой"])
        assert result.confidence == "low"
        assert result.needs_review is True
        assert "собрать" in result.next_steps[0].lower()


class TestSeedData:
    def test_load_jsonl_events(self, client):
        path = os.path.join(
            os.path.dirname(__file__), "..", "tests_data", "events.jsonl"
        )
        valid_count = 0
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                r = client.post("/events", json=data)
                if r.status_code == 201:
                    valid_count += 1
                else:
                    assert r.status_code == 422
        assert valid_count == 9
