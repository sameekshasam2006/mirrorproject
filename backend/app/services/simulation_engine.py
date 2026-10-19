from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.models import Simulation, SimulationAlternative, Task, User, UserPreference


PRIORITY_WEIGHT = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.replace(tzinfo=None)


def _get_user_preferences(db: Session, user_id: int) -> UserPreference | None:
    return db.query(UserPreference).filter(UserPreference.user_id == user_id).first()


def _serialize_task(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "category": task.category,
        "priority": task.priority,
        "status": task.status,
        "start_time": task.start_time.isoformat() if task.start_time else None,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "estimated_duration": task.estimated_duration,
        "actual_duration": task.actual_duration,
    }


def detect_conflicts(tasks: list[Task]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    items = [task for task in tasks if task.start_time]
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            a_start = _normalize_datetime(a.start_time)
            b_start = _normalize_datetime(b.start_time)
            a_end = _normalize_datetime(a.start_time) + timedelta(minutes=a.estimated_duration)
            b_end = _normalize_datetime(b.start_time) + timedelta(minutes=b.estimated_duration)
            if a_start and b_start and a_start < b_end and b_start < a_end:
                conflicts.append({
                    "task_a": a.title,
                    "task_b": b.title,
                    "start": max(a.start_time, b.start_time).isoformat(),
                    "end": min(a_end, b_end).isoformat(),
                })
    return conflicts


def calculate_workload(tasks: list[Task]) -> int:
    return sum(task.estimated_duration for task in tasks if task.status != "completed")


def calculate_free_time(preferences: UserPreference | None, tasks: list[Task]) -> int:
    if preferences is None:
        return 0
    try:
        start_hour, end_hour = preferences.available_hours.split("-")
        total = (int(end_hour) - int(start_hour)) * 60
    except ValueError:
        total = 480
    workload = calculate_workload(tasks)
    return max(total - workload, 0)


def _build_alternative_schedules(tasks: list[Task], preferences: UserPreference | None) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    pending = sorted(
        [task for task in tasks if task.status != "completed"],
        key=lambda task: (PRIORITY_WEIGHT.get(task.priority, 1), task.due_date or datetime.max),
        reverse=True,
    )

    for idx, task in enumerate(pending[:3]):
        alternative = {
            "title": f"Alternative {idx + 1}",
            "scheduled_tasks": [
                {
                    "id": task.id,
                    "title": task.title,
                    "priority": task.priority,
                    "start_time": (task.start_time + timedelta(hours=(idx + 1) * 2)).isoformat() if task.start_time else None,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                }
            ],
            "benefits": "Keeps the task on the calendar with a smaller impact on the rest of the day.",
            "drawbacks": "Moves the task later, which may compress adjacent work blocks.",
            "feasibility_result": "feasible",
        }
        candidates.append(alternative)
    return candidates[:3]


def simulate_decision(db: Session, user: User, task_id: int, scenario_type: str, new_time: datetime | None = None, new_duration: int | None = None, new_priority: str | None = None, move_to_date: datetime | None = None) -> tuple[Simulation, dict[str, Any]]:
    tasks = db.query(Task).filter(Task.user_id == user.id).all()
    target = next((task for task in tasks if task.id == task_id), None)
    if target is None:
        raise ValueError("Task not found")

    preferences = _get_user_preferences(db, user.id)
    original_snapshot = {"tasks": [_serialize_task(task) for task in tasks]}
    proposed_tasks = deepcopy(tasks)
    affected = []

    for task in proposed_tasks:
        if task.id == target.id:
            if scenario_type == "postpone":
                if task.start_time:
                    task.start_time = _normalize_datetime(task.start_time) + timedelta(hours=1)
                    if task.due_date:
                        task.due_date = _normalize_datetime(task.due_date) + timedelta(hours=1)
                affected.append(task.title)
            elif scenario_type == "skip":
                task.status = "completed"
                task.actual_duration = task.estimated_duration
                affected.append(task.title)
            elif scenario_type == "move":
                if new_time:
                    task.start_time = _normalize_datetime(new_time)
                elif move_to_date:
                    task.start_time = _normalize_datetime(move_to_date)
                affected.append(task.title)
            elif scenario_type == "extend":
                if new_duration:
                    task.estimated_duration = new_duration
                if task.start_time and task.due_date:
                    task.due_date = task.due_date + timedelta(minutes=max(new_duration or 0, 0))
                affected.append(task.title)
            elif scenario_type == "priority":
                if new_priority:
                    task.priority = new_priority
                affected.append(task.title)

    proposed_snapshot = {"tasks": [_serialize_task(task) for task in proposed_tasks]}
    conflicts = detect_conflicts(proposed_tasks)
    workload_before = calculate_workload(tasks)
    workload_after = calculate_workload(proposed_tasks)
    free_before = calculate_free_time(preferences, tasks)
    free_after = calculate_free_time(preferences, proposed_tasks)
    deadline_risk = [
        task.title for task in proposed_tasks if task.due_date and task.start_time and task.due_date < task.start_time + timedelta(minutes=task.estimated_duration)
    ]
    feasible = not conflicts and not deadline_risk and workload_after <= (calculate_free_time(preferences, []) + workload_after)
    impact = {
        "workload_before": workload_before,
        "workload_after": workload_after,
        "free_time_before": free_before,
        "free_time_after": free_after,
        "deadline_risk": deadline_risk,
        "conflicts": conflicts,
        "affected_tasks": affected,
        "feasible": feasible,
        "explanation": (
            "The proposed plan changes the selected task and keeps the rest of the schedule intact. "
            "Conflicts and deadline risks are surfaced before the plan is applied."
        ),
    }

    alternatives = [
        {
            "title": "Alternative 1",
            "proposed_schedule": {"tasks": [_serialize_task(task) for task in proposed_tasks]},
            "benefits": "Maintains the deadline and opens a small recovery window.",
            "drawbacks": "Calls for a later start time on the affected task.",
            "feasibility_result": "feasible" if feasible else "constrained",
        },
        {
            "title": "Alternative 2",
            "proposed_schedule": {"tasks": [_serialize_task(task) for task in tasks]},
            "benefits": "Keeps the current plan intact while reducing pressure on the affected task.",
            "drawbacks": "May postpone the task to a later day.",
            "feasibility_result": "feasible",
        },
    ]

    simulation = Simulation(
        user_id=user.id,
        title=f"{scenario_type.title()} plan",
        scenario_type=scenario_type,
        original_snapshot=original_snapshot,
        proposed_snapshot=proposed_snapshot,
        impact_analysis=impact,
        feasibility_result="feasible" if feasible else "constrained",
        status="draft",
    )
    db.add(simulation)
    db.flush()
    for alternative in alternatives:
        db.add(
            SimulationAlternative(
                simulation_id=simulation.id,
                title=alternative["title"],
                proposed_schedule=alternative["proposed_schedule"],
                benefits=alternative["benefits"],
                drawbacks=alternative["drawbacks"],
                feasibility_result=alternative["feasibility_result"],
            )
        )
    db.commit()
    db.refresh(simulation)
    return simulation, impact


def approve_simulation(db: Session, user: User, simulation_id: int) -> dict[str, Any]:
    simulation = db.query(Simulation).filter(Simulation.id == simulation_id, Simulation.user_id == user.id).first()
    if not simulation:
        raise ValueError("Simulation not found")

    proposed_tasks = simulation.proposed_snapshot.get("tasks", [])
    current_tasks = db.query(Task).filter(Task.user_id == user.id).all()
    current_map = {task.id: task for task in current_tasks}

    for item in proposed_tasks:
        task = current_map.get(item["id"])
        if not task:
            continue
        task.title = item["title"]
        task.description = item.get("description")
        task.category = item.get("category", task.category)
        task.priority = item.get("priority", task.priority)
        task.status = item.get("status", task.status)
        task.start_time = _normalize_datetime(datetime.fromisoformat(item["start_time"])) if item.get("start_time") else None
        task.due_date = _normalize_datetime(datetime.fromisoformat(item["due_date"])) if item.get("due_date") else None
        task.estimated_duration = item.get("estimated_duration", task.estimated_duration)
        task.actual_duration = item.get("actual_duration", task.actual_duration)
        task.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    simulation.status = "approved"
    simulation.applied_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"status": "approved", "simulation_id": simulation.id}
