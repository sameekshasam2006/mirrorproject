from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.calendar import router as calendar_router
from app.api.simulations import router as simulations_router
from app.api.tasks import router as tasks_router
from app.core.security import create_access_token
from app.db import Base, get_db
from app.models.models import Task, User, UserPreference


def test_authenticated_skip_simulation_history_approval_and_calendar_refresh():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    app = FastAPI()
    app.include_router(tasks_router, prefix="/tasks")
    app.include_router(calendar_router, prefix="/calendar")
    app.include_router(simulations_router, prefix="/simulations")

    def override_get_db():
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    today = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0, tzinfo=None)
    tomorrow = today + timedelta(days=1)
    with test_session() as db:
        user = User(email="planner@example.com", display_name="Planner", password_hash="hash")
        other_user = User(email="other-planner@example.com", display_name="Other", password_hash="hash")
        db.add_all([user, other_user])
        db.flush()
        db.add(UserPreference(user_id=user.id, available_hours="9-17", working_hours="09:00-17:00"))
        preparation = Task(
            user_id=user.id,
            title="Examination preparation",
            priority="critical",
            status="not_started",
            start_time=today,
            due_date=tomorrow.replace(hour=23, minute=59),
            estimated_duration=120,
        )
        exam = Task(
            user_id=user.id,
            title="Examination",
            priority="high",
            status="not_started",
            start_time=tomorrow,
            due_date=tomorrow.replace(hour=23, minute=59),
            estimated_duration=60,
        )
        db.add_all([preparation, exam])
        db.commit()
        preparation_id = preparation.id
        other_email = other_user.email
        user_email = user.email

    client = TestClient(app)
    user_headers = {"Authorization": f"Bearer {create_access_token(user_email)}"}
    other_headers = {"Authorization": f"Bearer {create_access_token(other_email)}"}
    assert client.get("/tasks/").status_code == 401

    simulation_response = client.post(
        "/simulations/run",
        headers=user_headers,
        json={"task_id": preparation_id, "scenario_type": "skip"},
    )
    assert simulation_response.status_code == 200
    simulation = simulation_response.json()
    assert simulation["proposed_snapshot"]["tasks"][0]["status"] == "not_started"
    assert len(simulation["alternatives"]) >= 2
    selected_alternative = simulation["alternatives"][0]
    proposed = next(
        task for task in selected_alternative["proposed_schedule"]["tasks"]
        if task["id"] == preparation_id
    )
    assert datetime.fromisoformat(proposed["start_time"]).date() == tomorrow.date()

    before_approval = client.get("/tasks/", headers=user_headers).json()
    saved_preparation = next(task for task in before_approval if task["id"] == preparation_id)
    assert saved_preparation["status"] == "not_started"
    assert datetime.fromisoformat(saved_preparation["start_time"]).date() == today.date()
    history = client.get("/simulations/history", headers=user_headers)
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert len(history.json()[0]["alternatives"]) >= 2
    assert client.get("/simulations/history", headers=other_headers).json() == []
    assert client.post(
        f'/simulations/{simulation["id"]}/approve',
        headers=other_headers,
        json={},
    ).status_code == 404

    approval = client.post(
        f'/simulations/{simulation["id"]}/approve',
        headers=user_headers,
        json={"alternative_id": selected_alternative["id"]},
    )
    assert approval.status_code == 200
    assert approval.json()["status"] == "approved"
    after_approval = client.get("/tasks/", headers=user_headers).json()
    saved_preparation = next(task for task in after_approval if task["id"] == preparation_id)
    assert saved_preparation["status"] == "not_started"
    assert datetime.fromisoformat(saved_preparation["start_time"]).date() == tomorrow.date()

    start = today.replace(hour=0)
    end = today + timedelta(days=3)
    calendar = client.get(
        f"/calendar/schedule?start={start.isoformat()}Z&end={end.isoformat()}Z",
        headers=user_headers,
    )
    assert calendar.status_code == 200
    calendar_task = next(task for task in calendar.json()["tasks"] if task["id"] == preparation_id)
    assert calendar_task["start_time"].startswith(tomorrow.date().isoformat())
    assert calendar_task["estimated_duration"] == 120

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
