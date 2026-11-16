from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db import get_db
from app.models.models import Task, User
from app.schemas.schemas import TaskCreate, TaskOut, TaskUpdate

router = APIRouter()


def _naive_utc(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


@router.get("/", response_model=list[TaskOut])
def list_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    sort: str = "due_date",
):
    query = db.query(Task).filter(Task.user_id == current_user.id)
    if search:
        query = query.filter(or_(Task.title.contains(search), Task.description.contains(search)))
    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    if sort == "due_date":
        query = query.order_by(Task.due_date.is_(None), Task.due_date.asc())
    elif sort == "priority":
        query = query.order_by(Task.priority.desc())
    elif sort == "status":
        query = query.order_by(Task.status.asc())
    return query.all()


@router.post("/", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    start_time = _naive_utc(payload.start_time)
    due_date = _naive_utc(payload.due_date)
    if due_date and start_time and due_date < start_time:
        raise HTTPException(status_code=400, detail="Due date cannot be before start time")

    task = Task(user_id=current_user.id, **payload.model_dump(exclude={"start_time", "due_date"}), start_time=start_time, due_date=due_date)
    db.add(task)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=TaskOut)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            if field in {"start_time", "due_date"}:
                value = _naive_utc(value)
            setattr(task, field, value)
    if task.due_date and task.start_time and task.due_date < task.start_time:
        db.rollback()
        raise HTTPException(status_code=400, detail="Due date cannot be before start time")
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
