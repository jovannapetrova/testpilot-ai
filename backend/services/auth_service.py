from __future__ import annotations

import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from models.database import User
from services.api_errors import raise_api_error
from services.database import get_db

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_token(user: User, token_type: str, expires_delta: timedelta) -> str:
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + expires_delta
    payload: dict[str, Any] = {
        "sub": user.id,
        "email": user.email,
        "type": token_type,
        "exp": expires_at,
        "iat": issued_at,
        "issued_at": issued_at.timestamp(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_access_token(user: User) -> str:
    return create_token(user, "access", timedelta(minutes=ACCESS_TOKEN_MINUTES))


def create_refresh_token(user: User) -> str:
    return create_token(user, "refresh", timedelta(days=REFRESH_TOKEN_DAYS))


def create_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_reset_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _as_utc_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    return None


def token_is_current_for_user(payload: dict[str, Any], user: User) -> bool:
    password_changed_at = _as_utc_datetime(getattr(user, "password_changed_at", None))
    if not password_changed_at:
        return True

    issued_at = _as_utc_datetime(payload.get("issued_at", payload.get("iat")))
    if not issued_at:
        return False

    return issued_at >= password_changed_at


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise_api_error(
            "SESSION_EXPIRED",
            "Your session is invalid or expired. Please sign in again.",
            status.HTTP_401_UNAUTHORIZED,
        )

    if payload.get("type") != expected_type:
        raise_api_error(
            "SESSION_EXPIRED",
            "Your session is invalid or expired. Please sign in again.",
            status.HTTP_401_UNAUTHORIZED,
        )

    return payload


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(token, "access")
    user = db.get(User, payload.get("sub"))

    if not user or not user.is_active:
        raise_api_error(
            "AUTH_REQUIRED",
            "User account is not available.",
            status.HTTP_401_UNAUTHORIZED,
        )

    if not token_is_current_for_user(payload, user):
        raise_api_error(
            "SESSION_EXPIRED",
            "Your password was changed. Please sign in again.",
            status.HTTP_401_UNAUTHORIZED,
        )

    return user


def public_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }
