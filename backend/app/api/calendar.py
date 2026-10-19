from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db import get_db
from app.models.models import Task, User

router = APIRouter()


@router.get("/schedule")
def get_schedule(
    start: datetime = Query(...),
    end: datetime = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if end < start:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    tasks = db.query(Task).filter(Task.user_id == current_user.id, Task.start_time != None).filter(Task.start_time >= start, Task.start_time <= end).all()
    return {"tasks": [
        {
            "id": task.id,
            "title": task.title,
            "start": task.start_time.isoformat() if task.start_time else None,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "priority": task.priority,
            "status": task.status,
            "duration": task.estimated_duration,
        }
        for task in tasks
    ]}


@router.get("/day")
def get_day_schedule(day: datetime = Query(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    start = datetime.combine(day.date(), datetime.min.time())
    end = start + timedelta(days=1)
    return get_schedule(start=start, end=end, db=db, current_user=current_user)
