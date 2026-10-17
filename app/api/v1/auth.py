"""Auth endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import AuthUser, Csrf, DbSession
from app.config import get_settings
from app.core.security import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    check_login_rate_limit,
    clear_login_attempts,
    create_session_token,
    new_csrf_token,
    register_failed_login,
    verify_password,
)

router = APIRouter(tags=["auth"])


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


@router.post("/auth/login")
def login(
    body: LoginBody,
    request: Request,
    response: Response,
) -> dict:
    settings = get_settings()
    ip = request.client.host if request.client else "unknown"
    check_login_rate_limit(ip)
    ok = (
        body.username == settings.admin_username
        and verify_password(body.password, settings.admin_password_hash)
    )
    if not ok:
        register_failed_login(ip)
        raise HTTPException(
            status_code=401,
            detail={
                "code": "unauthorized",
                "message": "Неверный логин или пароль",
            },
        )
    clear_login_attempts(ip)
    token = create_session_token(body.username, settings)
    csrf = new_csrf_token()
    secure = settings.is_production
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.session_ttl_hours * 3600,
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        httponly=False,
        secure=secure,
        samesite="lax",
        max_age=settings.session_ttl_hours * 3600,
    )
    return {"ok": True, "csrf_token": csrf}


@router.post("/auth/logout")
def logout(
    response: Response,
    _user: AuthUser,
    _csrf: Csrf,
) -> dict:
    response.delete_cookie(SESSION_COOKIE)
    response.delete_cookie(CSRF_COOKIE)
    return {"ok": True}
