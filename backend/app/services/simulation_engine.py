from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.models.models import Simulation, SimulationAlternative, Task, User, UserPreference


PRIORITY_WEIGHT = {"low": 1, "medium": 2, "high": 3, "critical": 4}
SUPPORTED_SCENARIOS = {"skip", "postpone", "move", "extend", "priority"}
_HORIZON_DAYS = 60


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _get_user_preferences(db: Session, user_id: int) -> UserPreference | None:
    return db.query(UserPreference).filter(UserPreference.user_id == user_id).first()


def _serialize_task(task: Task) -> dict[str, Any]:
    start_time = _normalize_datetime(task.start_time)
    due_date = _normalize_datetime(task.due_date)
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "category": task.category,
        "priority": task.priority,
        "status": task.status,
        "start_time": start_time.isoformat() if start_time else None,
        "due_date": due_date.isoformat() if due_date else None,
        "estimated_duration": task.estimated_duration,
        "actual_duration": task.actual_duration,
    }


def _parse_working_hours(preferences: UserPreference | None) -> tuple[int, int]:
    available = (preferences.available_hours if preferences else "") or ""
    available_match = re.fullmatch(r"\s*(\d{1,2})\s*-\s*(\d{1,2})\s*", available)
    available_range = None
    if available_match:
        start_hour, end_hour = map(int, available_match.groups())
        if 0 <= start_hour < end_hour <= 24:
            available_range = (start_hour * 60, end_hour * 60)

    working = (preferences.working_hours if preferences else "") or ""
    working_match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*", working)
    working_range = None
    if working_match:
        start_hour, start_minute, end_hour, end_minute = map(int, working_match.groups())
        start = start_hour * 60 + start_minute
        end = end_hour * 60 + end_minute
        if 0 <= start < end <= 24 * 60:
            working_range = (start, end)

    default_working_range = (9 * 60, 17 * 60)
    if working_range and working_range != default_working_range:
        return working_range
    if available_range:
        return available_range
    if working_range:
        return working_range
    return 9 * 60, 17 * 60


def _at_minute(day: date, minute: int) -> datetime:
    if minute == 24 * 60:
        return datetime.combine(day + timedelta(days=1), time.min)
    return datetime.combine(day, time(minute // 60, minute % 60))


def _task_end(task: dict[str, Any]) -> datetime | None:
    start = datetime.fromisoformat(task["start_time"]) if task.get("start_time") else None
    if start is None:
        return None
    return start + timedelta(minutes=int(task.get("estimated_duration") or 0))


def _intervals_conflict(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and start_b < end_a


def _conflicts_for_schedule(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    scheduled = [task for task in tasks if task.get("start_time") and task.get("status") != "completed"]
    for index, first in enumerate(scheduled):
        first_start = datetime.fromisoformat(first["start_time"])
        first_end = _task_end(first)
        if first_end is None:
            continue
        for second in scheduled[index + 1:]:
            second_start = datetime.fromisoformat(second["start_time"])
            second_end = _task_end(second)
            if second_end and _intervals_conflict(first_start, first_end, second_start, second_end):
                conflicts.append({
                    "task_a": first["title"],
                    "task_b": second["title"],
                    "start": max(first_start, second_start).isoformat(),
                    "end": min(first_end, second_end).isoformat(),
                })
    return conflicts


def detect_conflicts(tasks: list[Task]) -> list[dict[str, Any]]:
    return _conflicts_for_schedule([_serialize_task(task) for task in tasks])


def calculate_workload(tasks: list[Task]) -> int:
    return sum(task.estimated_duration for task in tasks if task.status != "completed")


def calculate_free_time(preferences: UserPreference | None, tasks: list[Task]) -> int:
    start_minute, end_minute = _parse_working_hours(preferences)
    return max(end_minute - start_minute - calculate_workload(tasks), 0)


def _find_slot(
    earliest: datetime,
    duration: int,
    busy: list[tuple[datetime, datetime]],
    working_start: int,
    working_end: int,
    latest_day: date,
) -> datetime | None:
    day = earliest.date()
    while day <= latest_day:
        day_start = _at_minute(day, working_start)
        day_end = _at_minute(day, working_end)
        candidate = max(day_start, earliest if day == earliest.date() else day_start)
        day_busy = sorted((start, end) for start, end in busy if start.date() == day)
        for busy_start, busy_end in day_busy:
            if candidate + timedelta(minutes=duration) <= busy_start:
                break
            if _intervals_conflict(candidate, candidate + timedelta(minutes=duration), busy_start, busy_end):
                candidate = max(candidate, busy_end)
        if candidate + timedelta(minutes=duration) <= day_end:
            return candidate
        day += timedelta(days=1)
        earliest = _at_minute(day, working_start)
    return None


def _ordered_tasks(tasks: list[dict[str, Any]], strategy: str, today: date) -> list[dict[str, Any]]:
    def due(task: dict[str, Any]) -> datetime:
        return datetime.fromisoformat(task["due_date"]) if task.get("due_date") else datetime.max

    if strategy == "deadline":
        return sorted(tasks, key=lambda task: (due(task), -PRIORITY_WEIGHT.get(task["priority"], 1), task["id"]))
    if strategy == "balanced":
        return sorted(tasks, key=lambda task: (
            0 if due(task).date() <= today + timedelta(days=2) else 1,
            -PRIORITY_WEIGHT.get(task["priority"], 1),
            due(task),
            task["id"],
        ))
    return sorted(tasks, key=lambda task: (
        -(PRIORITY_WEIGHT.get(task["priority"], 1) * 3 + (
            4 if due(task).date() <= today + timedelta(days=1) else
            3 if due(task).date() <= today + timedelta(days=3) else
            1 if due(task).date() <= today + timedelta(days=7) else 0
        )),
        due(task),
        task["id"],
    ))


def _reason_for(task: dict[str, Any], today: date) -> str:
    weight = PRIORITY_WEIGHT.get(task["priority"], 1)
    due = datetime.fromisoformat(task["due_date"]) if task.get("due_date") else None
    if due and due.date() <= today + timedelta(days=1):
        return "Deadline is imminent; this task is prioritized to protect its due date."
    if weight == 4:
        return "Critical priority places this task ahead of lower-impact work."
    if weight == 3:
        return "High priority and available capacity make this a strong next task."
    if due:
        return "Scheduled around existing commitments with its deadline in view."
    return "Placed in the next available working-time slot without overlapping existing tasks."


def _make_plan(
    base_tasks: list[dict[str, Any]],
    movable_ids: set[int],
    strategy: str,
    earliest_by_id: dict[int, datetime],
    preferences: UserPreference | None,
    today: date,
    start_offset_minutes: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    plan = [dict(task) for task in base_tasks]
    start_minute, end_minute = _parse_working_hours(preferences)
    busy: list[tuple[datetime, datetime]] = []
    movable: list[dict[str, Any]] = []
    for task in plan:
        if task["status"] == "completed":
            continue
        if task["id"] in movable_ids:
            movable.append(task)
            task["start_time"] = None
            continue
        if task.get("start_time"):
            start = datetime.fromisoformat(task["start_time"])
            busy.append((start, start + timedelta(minutes=task["estimated_duration"])))
        else:
            movable.append(task)

    recommendations: list[dict[str, Any]] = []
    latest_day = today + timedelta(days=_HORIZON_DAYS)
    for task in _ordered_tasks(movable, strategy, today):
        earliest = max(earliest_by_id.get(task["id"], datetime.combine(today, time.min)), datetime.combine(today, time.min))
        if start_offset_minutes:
            earliest = max(earliest, _at_minute(earliest.date(), start_minute)) + timedelta(minutes=start_offset_minutes)
        slot = _find_slot(earliest, int(task["estimated_duration"]), busy, start_minute, end_minute, latest_day)
        if slot is None:
            task["start_time"] = None
            continue
        task["start_time"] = slot.isoformat()
        busy.append((slot, slot + timedelta(minutes=int(task["estimated_duration"]))))
        due = datetime.fromisoformat(task["due_date"]) if task.get("due_date") else None
        task["recommendation_reason"] = _reason_for(task, today)
        recommendations.append({
            "task_id": task["id"],
            "task_name": task["title"],
            "date": slot.date().isoformat(),
            "start_time": slot.isoformat(),
            "estimated_duration": task["estimated_duration"],
            "priority": task["priority"],
            "priority_weight": PRIORITY_WEIGHT.get(task["priority"], 1),
            "due_date": due.isoformat() if due else None,
            "reason": task["recommendation_reason"],
        })
    for task in plan:
        if task["status"] != "completed" and task.get("start_time") and "recommendation_reason" not in task:
            task["recommendation_reason"] = "Kept at its existing scheduled time."
    return plan, recommendations


def _analyze_plan(
    tasks: list[dict[str, Any]],
    preferences: UserPreference | None,
    today: date,
) -> dict[str, Any]:
    pending = [task for task in tasks if task["status"] != "completed"]
    conflicts = _conflicts_for_schedule(tasks)
    deadline_risks = []
    for task in pending:
        end = _task_end(task)
        due = datetime.fromisoformat(task["due_date"]) if task.get("due_date") else None
        if due and (end is None or end > due):
            deadline_risks.append({
                "task_id": task["id"],
                "task_name": task["title"],
                "due_date": due.isoformat(),
                "scheduled_end": end.isoformat() if end else None,
            })

    start_minute, end_minute = _parse_working_hours(preferences)
    day_load: dict[date, int] = {}
    for task in pending:
        if task.get("start_time"):
            scheduled = datetime.fromisoformat(task["start_time"])
            day_load[scheduled.date()] = day_load.get(scheduled.date(), 0) + int(task["estimated_duration"])
    overloaded_days = [
        {"date": day.isoformat(), "scheduled_minutes": minutes, "available_minutes": end_minute - start_minute}
        for day, minutes in sorted(day_load.items())
        if minutes > end_minute - start_minute
    ]
    planning_day = min(day_load, default=today)
    occupied = day_load.get(planning_day, 0)
    free_today = max(end_minute - start_minute - occupied, 0)
    workload = sum(int(task["estimated_duration"]) for task in pending)
    risk_titles = {item["task_name"] for item in deadline_risks}
    conflict_titles = {item["task_a"] for item in conflicts} | {item["task_b"] for item in conflicts}
    attention = sorted(risk_titles | conflict_titles)
    priority_analysis = {
        name: [
            {"id": task["id"], "title": task["title"], "priority_weight": PRIORITY_WEIGHT[name]}
            for task in pending if task["priority"] == name
        ]
        for name in ("critical", "high", "medium", "low")
    }
    warnings = [
        {"type": "schedule_conflict", "message": f'{item["task_a"]} overlaps {item["task_b"]}.', **item}
        for item in conflicts
    ]
    warnings.extend(
        {"type": "deadline_risk", "message": f'{item["task_name"]} is scheduled after its deadline.', **item}
        for item in deadline_risks
    )
    warnings.extend(
        {"type": "overloaded_day", "message": f'{item["date"]} exceeds available working hours.', **item}
        for item in overloaded_days
    )
    return {
        "workload_minutes": workload,
        "free_time_minutes": free_today,
        "pending_task_count": len(pending),
        "conflicts": conflicts,
        "deadline_risks": deadline_risks,
        "overloaded_days": overloaded_days,
        "priority_analysis": priority_analysis,
        "postponable_tasks": [
            {"id": task["id"], "title": task["title"], "priority": task["priority"]}
            for task in pending if task["priority"] in {"low", "medium"} and task["title"] not in attention
        ],
        "tasks_requiring_attention": attention,
        "warnings": warnings,
        "planning_date": planning_day.isoformat(),
    }


def _make_alternative(
    title: str,
    base_tasks: list[dict[str, Any]],
    movable_ids: set[int],
    strategy: str,
    earliest_by_id: dict[int, datetime],
    preferences: UserPreference | None,
    today: date,
    benefit: str,
    drawback: str,
    start_offset_minutes: int = 0,
) -> dict[str, Any]:
    plan, recommendations = _make_plan(
        base_tasks,
        movable_ids,
        strategy,
        earliest_by_id,
        preferences,
        today,
        start_offset_minutes=start_offset_minutes,
    )
    analysis = _analyze_plan(plan, preferences, today)
    return {
        "title": title,
        "proposed_schedule": {"tasks": plan, "recommendations": recommendations, "impact_analysis": analysis},
        "benefits": benefit,
        "drawbacks": drawback,
        "feasibility_result": "feasible" if not analysis["conflicts"] and not analysis["deadline_risks"] and all(
            task["status"] == "completed" or task.get("start_time") for task in plan
        ) else "constrained",
    }


def simulate_decision(
    db: Session,
    user: User,
    task_id: int,
    scenario_type: str,
    new_time: datetime | None = None,
    new_duration: int | None = None,
    new_priority: str | None = None,
    move_to_date: datetime | None = None,
) -> tuple[Simulation, dict[str, Any]]:
    if scenario_type not in SUPPORTED_SCENARIOS:
        raise ValueError("Unsupported simulation scenario")
    if scenario_type == "move" and new_time is None and move_to_date is None:
        raise ValueError("Move requires a new time or date")
    if scenario_type == "extend" and new_duration is None:
        raise ValueError("Extend requires a new duration")
    if scenario_type == "priority" and new_priority is None:
        raise ValueError("Priority change requires a new priority")
    if new_priority is not None and new_priority.lower() not in PRIORITY_WEIGHT:
        raise ValueError("Priority must be low, medium, high, or critical")
    if new_duration is not None and not 15 <= new_duration <= 480:
        raise ValueError("Duration must be between 15 and 480 minutes")

    tasks = db.query(Task).filter(Task.user_id == user.id).order_by(Task.id).all()
    target = next((task for task in tasks if task.id == task_id), None)
    if target is None:
        raise ValueError("Task not found")
    if target.status == "completed" and scenario_type in {"skip", "postpone"}:
        raise ValueError("A completed task cannot be skipped or postponed")

    preferences = _get_user_preferences(db, user.id)
    today = datetime.now(timezone.utc).date()
    original_tasks = [_serialize_task(task) for task in tasks]
    proposed_tasks = [dict(task) for task in original_tasks]
    proposed_target = next(task for task in proposed_tasks if task["id"] == target.id)
    movable_ids: set[int] = set()
    earliest_by_id: dict[int, datetime] = {}
    original_start = _normalize_datetime(target.start_time)
    default_earliest = original_start or datetime.combine(today, time.min)

    if scenario_type in {"skip", "postpone"}:
        proposed_target["status"] = target.status
        movable_ids.add(target.id)
        proposed_target["start_time"] = None
        earliest_by_id[target.id] = datetime.combine(
            max((original_start.date() + timedelta(days=1)) if original_start else (today + timedelta(days=1)),
                today + timedelta(days=1)),
            time.min,
        )
    elif scenario_type == "move":
        movable_ids.add(target.id)
        if new_time is not None:
            proposed_target["start_time"] = _normalize_datetime(new_time).isoformat()
            movable_ids.remove(target.id)
        else:
            requested_date = _normalize_datetime(move_to_date)
            movable_ids.add(target.id)
            earliest_by_id[target.id] = datetime.combine(requested_date.date(), time.min)
    elif scenario_type == "extend":
        proposed_target["estimated_duration"] = new_duration
    elif scenario_type == "priority":
        proposed_target["priority"] = new_priority.lower()

    for task in proposed_tasks:
        if task["status"] != "completed" and task["id"] not in movable_ids and not task.get("start_time"):
            movable_ids.add(task["id"])
            earliest_by_id[task["id"]] = max(default_earliest, datetime.combine(today, time.min))

    proposed_tasks_plan, recommendations = _make_plan(
        proposed_tasks, movable_ids, "priority", earliest_by_id, preferences, today
    )
    analysis = _analyze_plan(proposed_tasks_plan, preferences, today)
    original_analysis = _analyze_plan(original_tasks, preferences, today)
    feasible = not analysis["conflicts"] and not analysis["deadline_risks"] and all(
        task["status"] == "completed" or task.get("start_time") for task in proposed_tasks_plan
    )

    alternatives = [
        _make_alternative(
            "Deadline-first plan", proposed_tasks, movable_ids, "deadline", earliest_by_id,
            preferences, today,
            "Schedules the nearest deadlines first, reducing the chance of late work.",
            "A lower-priority task with a later deadline may be pushed into a later slot.",
        ),
        _make_alternative(
            "Balanced-priority plan", proposed_tasks, movable_ids, "balanced", earliest_by_id,
            preferences, today,
            "Leaves a two-hour buffer after working hours begin for a less compressed focus block.",
            "The later start can increase deadline pressure when the day is already busy.",
            start_offset_minutes=120,
        ),
    ]

    target_plan = next(task for task in proposed_tasks_plan if task["id"] == target.id)
    impact = {
        "selected_task": {"id": target.id, "title": target.title},
        "scenario_type": scenario_type,
        "simulation_status": "draft",
        "workload_before": original_analysis["workload_minutes"],
        "workload_after": analysis["workload_minutes"],
        "free_time_before": original_analysis["free_time_minutes"],
        "free_time_after": analysis["free_time_minutes"],
        "available_time_minutes": analysis["free_time_minutes"],
        "pending_tasks_before": original_analysis["pending_task_count"],
        "pending_tasks_after": analysis["pending_task_count"],
        "feasible": feasible,
        "conflicts": analysis["conflicts"],
        "deadline_risks": analysis["deadline_risks"],
        "overloaded_days": analysis["overloaded_days"],
        "priority_analysis": analysis["priority_analysis"],
        "postponable_tasks": analysis["postponable_tasks"],
        "tasks_requiring_attention": analysis["tasks_requiring_attention"],
        "warnings": analysis["warnings"],
        "recommendations": recommendations,
        "original_recommendations": [
            {
                "task_id": task["id"], "task_name": task["title"], "start_time": task["start_time"],
                "estimated_duration": task["estimated_duration"], "priority": task["priority"],
            }
            for task in original_tasks if task["status"] != "completed" and task.get("start_time")
        ],
        "selected_task_recommendation": {
            "start_time": target_plan.get("start_time"),
            "status": target_plan["status"],
            "reason": target_plan.get("recommendation_reason"),
        },
        "planning_date": analysis["planning_date"],
        "explanation": (
            "The plan keeps completed work unchanged, respects existing scheduled commitments, and places "
            "pending work into preferred working hours. Review conflicts and deadline risks before approval."
        ),
    }
    simulation = Simulation(
        user_id=user.id,
        title=f"{scenario_type.title()} plan: {target.title}",
        scenario_type=scenario_type,
        original_snapshot={"tasks": original_tasks},
        proposed_snapshot={
            "tasks": proposed_tasks_plan,
            "recommendations": recommendations,
            "impact_analysis": analysis,
        },
        impact_analysis=impact,
        feasibility_result="feasible" if feasible else "constrained",
        status="draft",
    )
    try:
        db.add(simulation)
        db.flush()
        for alternative in alternatives:
            db.add(SimulationAlternative(simulation_id=simulation.id, **alternative))
        db.commit()
        db.refresh(simulation)
    except Exception:
        db.rollback()
        raise
    return simulation, impact


def approve_simulation(
    db: Session,
    user: User,
    simulation_id: int,
    alternative_id: int | None = None,
) -> dict[str, Any]:
    simulation = (
        db.query(Simulation)
        .options(selectinload(Simulation.alternatives))
        .filter(Simulation.id == simulation_id, Simulation.user_id == user.id)
        .first()
    )
    if not simulation:
        raise ValueError("Simulation not found")
    if simulation.status != "draft":
        raise ValueError("Only a draft simulation can be approved")

    selected_plan = simulation.proposed_snapshot
    selected_name = "Recommended plan"
    if alternative_id is not None:
        alternative = next((item for item in simulation.alternatives if item.id == alternative_id), None)
        if alternative is None:
            raise ValueError("Alternative plan not found")
        selected_plan = alternative.proposed_schedule
        selected_name = alternative.title

    proposed_tasks = selected_plan.get("tasks", [])
    current_tasks = db.query(Task).filter(Task.user_id == user.id).all()
    current_map = {task.id: task for task in current_tasks}
    try:
        for item in proposed_tasks:
            task = current_map.get(item["id"])
            if task is None:
                raise ValueError("A task in this plan no longer exists; run a new simulation")
            task.priority = item.get("priority", task.priority)
            task.status = item.get("status", task.status)
            task.start_time = _normalize_datetime(datetime.fromisoformat(item["start_time"])) if item.get("start_time") else None
            task.due_date = _normalize_datetime(datetime.fromisoformat(item["due_date"])) if item.get("due_date") else None
            task.estimated_duration = item.get("estimated_duration", task.estimated_duration)
            task.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        simulation.status = "approved"
        simulation.applied_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"status": "approved", "simulation_id": simulation.id, "selected_plan": selected_name}


def cancel_simulation(db: Session, user: User, simulation_id: int) -> dict[str, Any]:
    simulation = db.query(Simulation).filter(
        Simulation.id == simulation_id,
        Simulation.user_id == user.id,
    ).first()
    if simulation is None:
        raise ValueError("Simulation not found")
    if simulation.status != "draft":
        raise ValueError("Only a draft simulation can be cancelled")
    simulation.status = "cancelled"
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"status": "cancelled", "simulation_id": simulation.id}
