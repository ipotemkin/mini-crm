"""Login / logout pages."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.core.security import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    check_login_rate_limit,
    clear_login_attempts,
    create_session_token,
    get_current_user,
    new_csrf_token,
    register_failed_login,
    verify_password,
)
from app.web.deps import render

router = APIRouter(tags=["web-auth"])


@router.get("/login")
def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse("/", status_code=302)
    return render(request, "login.html")


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    settings = get_settings()
    ip = request.client.host if request.client else "unknown"
    try:
        check_login_rate_limit(ip)
    except Exception:
        return render(
            request,
            "login.html",
            {"error": "Слишком много попыток. Подождите 5 минут."},
            status_code=429,
        )
    ok = (
        username == settings.admin_username
        and verify_password(password, settings.admin_password_hash)
    )
    if not ok:
        register_failed_login(ip)
        return render(
            request,
            "login.html",
            {"error": "Неверный логин или пароль", "username": username},
            status_code=401,
        )
    clear_login_attempts(ip)
    response = RedirectResponse("/", status_code=302)
    token = create_session_token(username, settings)
    csrf = new_csrf_token()
    secure = settings.is_production
    max_age = settings.session_ttl_hours * 3600
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=max_age,
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        httponly=False,
        secure=secure,
        samesite="lax",
        max_age=max_age,
    )
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    response.delete_cookie(CSRF_COOKIE)
    return response
