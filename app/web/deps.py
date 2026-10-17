"""Web dependencies and template helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse

from app.config import get_settings
from app.core import enums
from app.core.security import CSRF_COOKIE, get_current_user, new_csrf_token
from app.core.timeutils import format_date, format_datetime, format_money
from app.db import get_db
from app.export.exporter import export_status
from app.services import tasks as task_svc

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

def _fmt_money(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, int):
        return format_money(value)
    from decimal import Decimal

    from app.core.money import to_kopecks

    return format_money(to_kopecks(Decimal(str(value))))


templates.env.filters["fmt_date"] = format_date
templates.env.filters["fmt_dt"] = format_datetime
templates.env.filters["fmt_money"] = _fmt_money
templates.env.filters["fmt_kopecks"] = format_money
templates.env.globals["CLIENT_STATUS_LABELS"] = {
    k.value: v for k, v in enums.CLIENT_STATUS_LABELS.items()
}
templates.env.globals["CLIENT_TYPE_LABELS"] = {
    k.value: v for k, v in enums.CLIENT_TYPE_LABELS.items()
}
templates.env.globals["DEAL_STATUS_LABELS"] = {
    k.value: v for k, v in enums.DEAL_STATUS_LABELS.items()
}
templates.env.globals["ORDER_STATUS_LABELS"] = {
    k.value: v for k, v in enums.ORDER_STATUS_LABELS.items()
}
templates.env.globals["TASK_TYPE_LABELS"] = {
    k.value: v for k, v in enums.TASK_TYPE_LABELS.items()
}
templates.env.globals["DUE_STATE_LABELS"] = enums.DUE_STATE_LABELS


def require_web_user(request: Request):
    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    return user


def ensure_csrf(request: Request, response) -> str:
    token = request.cookies.get(CSRF_COOKIE)
    if not token:
        token = new_csrf_token()
        settings = get_settings()
        response.set_cookie(
            CSRF_COOKIE,
            token,
            httponly=False,
            secure=settings.is_production,
            samesite="lax",
            max_age=settings.session_ttl_hours * 3600,
        )
    return token


def render(
    request: Request,
    name: str,
    context: dict[str, Any] | None = None,
    status_code: int = 200,
):
    from starlette.responses import HTMLResponse

    ctx = dict(context or {})
    ctx["request"] = request
    user = get_current_user(request)
    ctx["user"] = user
    csrf = request.cookies.get(CSRF_COOKIE) or ""
    ctx["csrf_token"] = csrf
    settings = get_settings()
    ctx["app_currency"] = settings.app_currency
    ctx["flash"] = request.query_params.get("flash")
    ctx["flash_error"] = request.query_params.get("error")
    if user:
        db = next(get_db())
        try:
            ctx["reminders"] = task_svc.reminder_summary(db)
            ctx["google_status"] = export_status(db)
        finally:
            db.close()
    else:
        ctx["reminders"] = None
        ctx["google_status"] = None
    html = templates.get_template(name).render(ctx)
    response = HTMLResponse(html, status_code=status_code)
    if user and not request.cookies.get(CSRF_COOKIE):
        ensure_csrf(request, response)
        # re-render with csrf if needed — cookie set for next request
    return response


def redirect_login() -> RedirectResponse:
    return RedirectResponse("/login", status_code=302)


def qs(**kwargs: Any) -> str:
    items = {k: v for k, v in kwargs.items() if v not in (None, "", [])}
    return urlencode(items, doseq=True)
