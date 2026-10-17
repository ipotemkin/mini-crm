"""Auth session, CSRF, password hashing, login rate limit."""

from __future__ import annotations

import secrets
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Annotated

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import Settings, get_settings

SESSION_COOKIE = "session"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"


@dataclass
class SessionUser:
    username: str


_login_attempts: dict[str, list[float]] = defaultdict(list)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except ValueError:
        return False


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        settings.secret_key,
        salt="mini-crm-session",
    )


def create_session_token(username: str, settings: Settings) -> str:
    return _serializer(settings).dumps({"u": username})


def read_session_token(
    token: str,
    settings: Settings,
) -> SessionUser | None:
    max_age = settings.session_ttl_hours * 3600
    try:
        data = _serializer(settings).loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    username = data.get("u")
    if not username:
        return None
    return SessionUser(username=username)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def check_login_rate_limit(ip: str) -> None:
    now = time.time()
    window = 300
    attempts = [t for t in _login_attempts[ip] if now - t < window]
    _login_attempts[ip] = attempts
    if len(attempts) >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "too_many_requests",
                "message": (
                    "Слишком много попыток входа. "
                    "Повторите через 5 минут."
                ),
            },
        )


def register_failed_login(ip: str) -> None:
    _login_attempts[ip].append(time.time())


def clear_login_attempts(ip: str) -> None:
    _login_attempts.pop(ip, None)


def get_current_user(request: Request) -> SessionUser | None:
    settings = get_settings()
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return read_session_token(token, settings)


def require_user(
    request: Request,
) -> SessionUser:
    user = get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "unauthorized",
                "message": "Требуется авторизация",
            },
        )
    return user


def verify_csrf(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    cookie_token = request.cookies.get(CSRF_COOKIE)
    header_token = request.headers.get(CSRF_HEADER)
    form_token = None
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        # Form CSRF checked in web handlers via Form()
        return
    if header_token is None:
        header_token = form_token
    if (
        not cookie_token
        or not header_token
        or not secrets.compare_digest(cookie_token, header_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "csrf_failed",
                "message": "Неверный CSRF-токен",
            },
        )


CurrentUser = Annotated[SessionUser, Depends(require_user)]
