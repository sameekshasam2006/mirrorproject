from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db import get_db
from app.models.models import User, UserPreference
from app.schemas.schemas import UserOut, UserPreferencesOut, UserPreferencesUpdate

router = APIRouter()


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.get("/preferences", response_model=UserPreferencesOut)
def get_preferences(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    prefs = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if not prefs:
        prefs = UserPreference(user_id=current_user.id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


@router.put("/preferences", response_model=UserPreferencesOut)
def update_preferences(payload: UserPreferencesUpdate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    prefs = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if not prefs:
        prefs = UserPreference(user_id=current_user.id)
        db.add(prefs)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(prefs, field, value)
    db.commit()
    db.refresh(prefs)
    return prefs


@router.put("/profile", response_model=UserOut)
def update_profile(payload: dict, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if "display_name" in payload and payload["display_name"]:
        current_user.display_name = payload["display_name"]
    if "time_zone" in payload and payload["time_zone"]:
        current_user.time_zone = payload["time_zone"]
    db.commit()
    db.refresh(current_user)
    return current_user
