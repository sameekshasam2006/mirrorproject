from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from app.core.security import get_password_hash, verify_password
from app.db import Base
from app.models.models import SimulationAlternative, Task, User, UserPreference
from app.schemas.schemas import SimulationInput
from app.services.simulation_engine import (
    approve_simulation,
    calculate_workload,
    cancel_simulation,
    detect_conflicts,
    simulate_decision,
)


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


def test_skip_keeps_task_pending_and_recommends_next_day_without_applying():
    db, user, target, exam = build_db()
    today = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    target.title = "Examination preparation"
    target.priority = "critical"
    target.start_time = today
    target.due_date = tomorrow.replace(hour=23, minute=59)
    target.estimated_duration = 120
    exam.title = "Examination"
    exam.priority = "high"
    exam.start_time = tomorrow.replace(hour=9)
    exam.due_date = tomorrow.replace(hour=23, minute=59)
    exam.estimated_duration = 60
    db.commit()

    simulation, impact = simulate_decision(db, user, target.id, "skip")
    proposed = {task["id"]: task for task in simulation.proposed_snapshot["tasks"]}
    recommendation = next(item for item in impact["recommendations"] if item["task_id"] == target.id)
    alternative_starts = [
        next(task["start_time"] for task in alternative.proposed_schedule["tasks"] if task["id"] == target.id)
        for alternative in simulation.alternatives
    ]
    saved_target = db.query(Task).filter(Task.id == target.id).first()

    assert proposed[target.id]["status"] == "not_started"
    assert datetime.fromisoformat(proposed[target.id]["start_time"]).date() == tomorrow.date()
    assert recommendation["priority_weight"] == 4
    assert recommendation["estimated_duration"] == 120
    assert impact["available_time_minutes"] > 0
    assert impact["pending_tasks_after"] == 2
    assert impact["conflicts"] == []
    assert len(simulation.alternatives) >= 2
    assert alternative_starts[0] != alternative_starts[1]
    assert all(alternative.feasibility_result == "feasible" for alternative in simulation.alternatives)
    assert db.query(SimulationAlternative).filter(SimulationAlternative.simulation_id == simulation.id).count() >= 2
    assert saved_target.status == "not_started"
    assert saved_target.start_time.date() == today.date()
    db.close()


def test_move_to_date_uses_available_working_time_and_does_not_apply():
    db, user, target, _ = build_db()
    desired_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=3)

    simulation, _ = simulate_decision(db, user, target.id, "move", move_to_date=desired_day)
    proposed = next(task for task in simulation.proposed_snapshot["tasks"] if task["id"] == target.id)

    assert datetime.fromisoformat(proposed["start_time"]).date() == desired_day.date()
    assert datetime.fromisoformat(proposed["start_time"]).hour == 9
    assert target.start_time.date() != desired_day.date()
    db.close()


def test_extend_and_priority_scenarios_update_simulated_plan():
    db, user, target, _ = build_db()
    extended, _ = simulate_decision(db, user, target.id, "extend", new_duration=180)
    extended_task = next(task for task in extended.proposed_snapshot["tasks"] if task["id"] == target.id)
    prioritized, impact = simulate_decision(db, user, target.id, "priority", new_priority="critical")
    prioritized_task = next(task for task in prioritized.proposed_snapshot["tasks"] if task["id"] == target.id)

    assert extended_task["estimated_duration"] == 180
    assert prioritized_task["priority"] == "critical"
    assert any(item["id"] == target.id and item["priority_weight"] == 4 for item in impact["priority_analysis"]["critical"])
    db.close()


def test_postpone_and_move_time_create_unapplied_proposals():
    db, user, target, _ = build_db()
    old_start = target.start_time
    postponed, _ = simulate_decision(db, user, target.id, "postpone")
    postponed_task = next(task for task in postponed.proposed_snapshot["tasks"] if task["id"] == target.id)
    moved_time = datetime.now() + timedelta(days=2, hours=2)
    moved, _ = simulate_decision(db, user, target.id, "move", new_time=moved_time)
    moved_task = next(task for task in moved.proposed_snapshot["tasks"] if task["id"] == target.id)

    assert datetime.fromisoformat(postponed_task["start_time"]) > old_start
    assert datetime.fromisoformat(moved_task["start_time"]) == moved_time
    assert target.start_time == old_start
    db.close()


def test_simulation_scenario_parameters_are_validated():
    with pytest.raises(ValueError):
        SimulationInput(task_id=1, scenario_type="move")
    with pytest.raises(ValueError):
        SimulationInput(task_id=1, scenario_type="extend")
    with pytest.raises(ValueError):
        SimulationInput(task_id=1, scenario_type="priority", new_priority="urgent")


def test_alternative_approval_updates_schedule_and_other_users_cannot_access_simulation():
    db, user, target, _ = build_db()
    simulation, _ = simulate_decision(db, user, target.id, "skip")
    alternative_id = simulation.alternatives[0].id
    alternative_start = next(
        task["start_time"] for task in simulation.alternatives[0].proposed_schedule["tasks"]
        if task["id"] == target.id
    )
    result = approve_simulation(db, user, simulation.id, alternative_id=alternative_id)
    db.refresh(target)

    assert result["selected_plan"] == simulation.alternatives[0].title
    assert target.status == "not_started"
    assert target.start_time.isoformat() == alternative_start
    assert simulation.status == "approved"

    other_user = User(email=f"other-{uuid4().hex[:8]}@example.com", display_name="Other", password_hash="hash")
    db.add(other_user)
    db.commit()
    with pytest.raises(ValueError, match="Simulation not found"):
        approve_simulation(db, other_user, simulation.id)
    db.close()


def test_conflict_deadline_warning_and_cancel_leave_real_tasks_unchanged():
    db, user, target, second = build_db()
    target.due_date = target.start_time + timedelta(minutes=30)
    original_start = target.start_time
    db.commit()

    simulation, impact = simulate_decision(db, user, target.id, "priority", new_priority="critical")
    assert impact["conflicts"]
    assert impact["deadline_risks"]
    assert any(item["type"] == "schedule_conflict" for item in impact["warnings"])
    assert any(item["type"] == "deadline_risk" for item in impact["warnings"])

    result = cancel_simulation(db, user, simulation.id)
    db.refresh(target)
    assert result["status"] == "cancelled"
    assert simulation.status == "cancelled"
    assert target.start_time == original_start
    assert target.priority == "high"
    db.close()


def test_available_hours_preference_controls_recommendation_slots():
    db, user, target, second = build_db()
    preference = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    preference.available_hours = "10-18"
    preference.working_hours = "09:00-17:00"
    target.start_time = None
    second.status = "completed"
    db.commit()

    simulation, _ = simulate_decision(db, user, target.id, "priority", new_priority="critical")
    proposed = next(task for task in simulation.proposed_snapshot["tasks"] if task["id"] == target.id)

    assert datetime.fromisoformat(proposed["start_time"]).hour == 10
    db.close()
