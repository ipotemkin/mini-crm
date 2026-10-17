"""Google OAuth start/callback for UI."""

from __future__ import annotations

import secrets
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.export import drive, oauth, token_store
from app.web.deps import require_web_user

router = APIRouter(tags=["web-google"])

# session-scoped PKCE store (single-user MVP)
_oauth_pending: dict[str, dict] = {}


@router.get("/settings/google/oauth/start")
def oauth_start(
    request: Request,
    _user=Depends(require_web_user),
):
    state = secrets.token_urlsafe(24)
    verifier, challenge = oauth.generate_pkce()
    _oauth_pending[state] = {
        "verifier": verifier,
        "expires": time.time() + 600,
    }
    # cleanup
    now = time.time()
    for key in list(_oauth_pending):
        if _oauth_pending[key]["expires"] < now:
            _oauth_pending.pop(key, None)
    url = oauth.build_auth_url(state, challenge)
    return RedirectResponse(url, status_code=302)


@router.get("/settings/google/oauth/callback")
def oauth_callback(
    request: Request,
    db: Session = Depends(get_db),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    _user=Depends(require_web_user),
):
    if error:
        return RedirectResponse(
            f"/settings?error=Доступ+к+Google+Drive+не+выдан",
            status_code=302,
        )
    pending = _oauth_pending.pop(state or "", None)
    if not pending or pending["expires"] < time.time():
        return RedirectResponse(
            "/settings?error=Сессия+OAuth+истекла",
            status_code=302,
        )
    if not code:
        return RedirectResponse(
            "/settings?error=Нет+кода+авторизации",
            status_code=302,
        )
    try:
        tokens = oauth.exchange_code(code, pending["verifier"])
        scope = tokens.get("scope", "")
        oauth.ensure_drive_scope(scope)
        refresh = tokens.get("refresh_token")
        access = tokens.get("access_token")
        if not refresh:
            # keep old refresh if Google didn't re-issue
            old = token_store.get_refresh_token(db)
            if not old:
                return RedirectResponse(
                    "/settings?error=Не+получен+refresh+token."
                    "+Отключите+доступ+и+подключите+снова",
                    status_code=302,
                )
            refresh = old
        email = oauth.fetch_user_email(access)
        token_store.save_credentials(
            db,
            email=email,
            scopes=scope,
            refresh_token=refresh,
        )
        drive.ensure_default_folder(db)
        return RedirectResponse(
            f"/settings?flash=Google-аккаунт+{email}+подключён",
            status_code=302,
        )
    except Exception as exc:
        return RedirectResponse(
            f"/settings?error={exc}",
            status_code=302,
        )
