from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db import get_db
from app.models.models import Task, User

router = APIRouter()


def _naive_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


@router.get("/schedule")
def get_schedule(
    start: datetime = Query(...),
    end: datetime = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    start = _naive_utc(start)
    end = _naive_utc(end)
    if end < start:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    tasks = (
        db.query(Task)
        .filter(Task.user_id == current_user.id, Task.start_time.is_not(None), Task.start_time <= end)
        .order_by(Task.start_time.asc())
        .all()
    )
    tasks = [
        task for task in tasks
        if task.start_time and task.start_time + timedelta(minutes=task.estimated_duration) >= start
    ]
    return {"tasks": [
        {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "category": task.category,
            "start": task.start_time.isoformat() if task.start_time else None,
            "start_time": task.start_time.isoformat() if task.start_time else None,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "priority": task.priority,
            "status": task.status,
            "duration": task.estimated_duration,
            "estimated_duration": task.estimated_duration,
        }
        for task in tasks
    ]}


@router.get("/day")
def get_day_schedule(day: datetime = Query(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    start = datetime.combine(day.date(), datetime.min.time())
    end = start + timedelta(days=1)
    return get_schedule(start=start, end=end, db=db, current_user=current_user)
