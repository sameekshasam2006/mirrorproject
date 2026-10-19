import smtplib
import secrets
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import create_access_token, get_current_active_user, get_password_hash, verify_password
from app.db import get_db
from app.models.models import User, UserPreference
from app.schemas.schemas import UserCreate, UserLogin, UserOut

router = APIRouter()


def _password_reset_email_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from_email) and (
        bool(settings.smtp_username) == bool(settings.smtp_password)
    )


def send_password_reset_email(email: str, reset_link: str) -> None:
    if not _password_reset_email_configured():
        raise HTTPException(status_code=503, detail="Password reset email is not configured")

    message = EmailMessage()
    message["Subject"] = "Reset your MIRROR password"
    message["From"] = settings.smtp_from_email
    message["To"] = email
    message.set_content(
        "Use the following link to reset your MIRROR password. "
        f"This link expires in 30 minutes:\n\n{reset_link}"
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls(context=ssl.create_default_context())
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise HTTPException(
            status_code=503,
            detail="Password reset email could not be sent. Please try again later.",
        ) from exc


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    if payload.password != payload.password_confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    user = User(
        email=payload.email,
        display_name=payload.display_name,
        password_hash=get_password_hash(payload.password),
        time_zone="UTC",
    )
    db.add(user)
    db.flush()
    db.add(UserPreference(user_id=user.id))
    db.commit()
    db.refresh(user)
    return user


@router.post("/login")
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(user.email, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer", "user": {"id": user.id, "email": user.email, "display_name": user.display_name}}


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.post("/forgot-password")
def forgot_password(payload: dict, db: Session = Depends(get_db)):
    email = str(payload.get("email", "")).strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    if not _password_reset_email_configured():
        raise HTTPException(status_code=503, detail="Password reset email is not configured")

    user = db.query(User).filter(User.email == email).first()
    if user:
        token = secrets.token_urlsafe(32)
        user.password_reset_token = token
        user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        db.commit()

        query = urlencode({"token": token, "email": email})
        reset_link = f"{settings.frontend_origin}/reset-password?{query}"
        send_password_reset_email(email, reset_link)

    return {
        "status": "success",
        "message": "If an account exists for this email, a password reset link has been sent.",
    }


@router.post("/reset-password")
def reset_password(payload: dict, db: Session = Depends(get_db)):
    email = str(payload.get("email", "")).strip().lower()
    token = str(payload.get("token", "")).strip()
    password = str(payload.get("password", ""))
    password_confirm = str(payload.get("password_confirm", ""))

    if not email or not token or not password or not password_confirm:
        raise HTTPException(status_code=400, detail="Email, token, and password are required")
    if password != password_confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.password_reset_token or user.password_reset_token != token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    expires_at = user.password_reset_expires_at
    if expires_at is None:
        user.password_reset_token = None
        user.password_reset_expires_at = None
        db.commit()
        raise HTTPException(status_code=400, detail="Reset token has expired")
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        user.password_reset_token = None
        user.password_reset_expires_at = None
        db.commit()
        raise HTTPException(status_code=400, detail="Reset token has expired")

    user.password_hash = get_password_hash(password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    db.commit()
    return {"status": "success", "message": "Password reset successfully"}


@router.post("/logout")
def logout_user():
    return {"message": "Logged out successfully"}
