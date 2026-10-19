from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db import get_db
from app.models.models import Task, User

router = APIRouter()


@router.get("/summary")
def summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    now = datetime.now(timezone.utc)
    tasks = db.query(Task).filter(Task.user_id == current_user.id).all()
    normalized_now = now.replace(tzinfo=None)
    completed = sum(1 for task in tasks if task.status == "completed")
    pending = sum(1 for task in tasks if task.status != "completed")
    overdue = sum(1 for task in tasks if task.due_date and task.due_date.replace(tzinfo=None) < normalized_now and task.status != "completed")

    workload_by_day = []
    for i in range(7):
        day = (now - timedelta(days=6 - i)).date().isoformat()
        value = sum(task.estimated_duration for task in tasks if task.start_time and task.start_time.date().isoformat() == day)
        workload_by_day.append({"day": day, "hours": value / 60})

    priority_distribution = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for task in tasks:
        priority_distribution[task.priority] = priority_distribution.get(task.priority, 0) + 1

    weekly_trend = [{"week": f"W{i + 1}", "tasks": sum(1 for task in tasks if task.created_at and task.created_at.isocalendar()[1] == (now.isocalendar()[1] - 2 + i))} for i in range(4)]

    return {
        "total_tasks": len(tasks),
        "completed_tasks": completed,
        "pending_tasks": pending,
        "overdue_tasks": overdue,
        "workload_by_day": workload_by_day,
        "priority_distribution": priority_distribution,
        "weekly_trend": weekly_trend,
    }
