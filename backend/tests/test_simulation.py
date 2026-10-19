from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import get_password_hash, verify_password
from app.db import Base
from app.models.models import Task, User, UserPreference
from app.services.simulation_engine import approve_simulation, calculate_workload, detect_conflicts, simulate_decision


engine = create_engine("sqlite://")
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)


def build_db():
    db = SessionLocal()
    email = f"demo-{uuid4().hex[:8]}@example.com"
    user = User(email=email, display_name="Demo User", password_hash="hash")
    db.add(user)
    db.flush()
    db.add(UserPreference(user_id=user.id, available_hours="9-17"))
    now = datetime.now(timezone.utc)
    first = Task(
        user_id=user.id,
        title="Deep work",
        description="Design sprint",
        priority="high",
        status="not_started",
        start_time=now,
        due_date=now + timedelta(hours=2),
        estimated_duration=120,
    )
    second = Task(
        user_id=user.id,
        title="Inbox review",
        description="Reply to threads",
        priority="medium",
        status="not_started",
        start_time=now + timedelta(minutes=60),
        due_date=now + timedelta(hours=3),
        estimated_duration=60,
    )
    db.add_all([first, second])
    db.commit()
    db.refresh(user)
    return db, user, first, second


def test_detect_conflicts_and_workload():
    db, user, first, second = build_db()
    assert len(detect_conflicts([first, second])) >= 1
    assert calculate_workload([first, second]) == 180
    db.close()


def test_simulate_decision_postpone():
    db, user, first, second = build_db()
    simulation, impact = simulate_decision(db, user, first.id, "postpone")
    assert simulation.scenario_type == "postpone"
    assert impact["workload_before"] > 0
    assert simulation.original_snapshot["tasks"][0]["id"] == first.id
    db.close()


def test_approve_simulation_updates_task():
    db, user, first, second = build_db()
    simulation, _ = simulate_decision(db, user, first.id, "move", new_time=datetime.now(timezone.utc) + timedelta(hours=4))
    result = approve_simulation(db, user, simulation.id)
    updated = db.query(Task).filter(Task.id == first.id).first()
    assert result["status"] == "approved"
    assert updated.start_time is not None
    assert simulation.applied_at is not None
    db.close()


def test_password_hash_accepts_longer_user_passwords():
    password = "a" * 200
    hashed = get_password_hash(password)
    assert verify_password(password, hashed) is True
