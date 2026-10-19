from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException

from app.api import auth
from app.config import settings
from app.core.security import get_password_hash
from app.models.models import User

from test_simulation import build_db


def test_forgot_password_requires_mail_configuration(monkeypatch):
    db, user, *_ = build_db()
    monkeypatch.setattr(settings, "smtp_host", None)
    monkeypatch.setattr(settings, "smtp_from_email", None)

    with pytest.raises(HTTPException) as error:
        auth.forgot_password({"email": user.email}, db)

    assert error.value.status_code == 503
    db.refresh(user)
    assert user.password_reset_token is None
    db.close()


def test_forgot_password_sends_link_without_returning_token(monkeypatch):
    db, user, *_ = build_db()
    sent = {}
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_from_email", "support@example.com")
    monkeypatch.setattr(settings, "smtp_username", None)
    monkeypatch.setattr(settings, "smtp_password", None)
    monkeypatch.setattr(auth, "send_password_reset_email", lambda email, link: sent.update(email=email, link=link))

    result = auth.forgot_password({"email": user.email}, db)
    query = parse_qs(urlparse(sent["link"]).query)

    assert sent["email"] == user.email
    assert query["email"] == [user.email]
    assert "token" in query
    assert "token" not in result
    assert "reset_link" not in result
    db.close()


def test_expired_sqlite_reset_token_returns_http_error():
    db, user, *_ = build_db()
    user.password_hash = get_password_hash("old password")
    user.password_reset_token = "expired-token"
    user.password_reset_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    with pytest.raises(HTTPException) as error:
        auth.reset_password(
            {
                "email": user.email,
                "token": "expired-token",
                "password": "new password",
                "password_confirm": "new password",
            },
            db,
        )

    assert error.value.status_code == 400
    assert error.value.detail == "Reset token has expired"
    db.refresh(user)
    assert user.password_reset_token is None
    db.close()
