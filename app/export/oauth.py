"""Google OAuth 2.0 flow with PKCE."""

from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import AppError
from app.core.timeutils import utc_now
from app.export import token_store
from app.models.settings import AppSetting

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/drive.file",
]

# In-memory access token cache
_access_token: str | None = None
_access_expiry: float = 0


def generate_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def build_auth_url(state: str, code_challenge: str) -> str:
    settings = get_settings()
    if not settings.google_configured:
        raise AppError(
            "export_not_configured",
            "Экспорт не настроен администратором",
            status_code=503,
        )
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.oauth_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        params
    )


def exchange_code(
    code: str,
    code_verifier: str,
) -> dict[str, Any]:
    settings = get_settings()
    data = {
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "code": code,
        "code_verifier": code_verifier,
        "grant_type": "authorization_code",
        "redirect_uri": settings.oauth_redirect_uri,
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            "https://oauth2.googleapis.com/token",
            data=data,
        )
    if resp.status_code != 200:
        raise AppError(
            "google_reauth_required",
            "Не удалось обменять код авторизации Google",
            status_code=502,
        )
    return resp.json()


def fetch_user_email(access_token: str) -> str:
    with httpx.Client(timeout=15) as client:
        resp = client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code != 200:
        return "unknown"
    return resp.json().get("email", "unknown")


def ensure_drive_scope(scope_str: str) -> None:
    if "drive.file" not in scope_str:
        raise AppError(
            "bad_request",
            "Не выдан доступ к Google Drive. "
            "Повторите подключение и разрешите доступ к файлам",
            status_code=400,
        )


def get_credentials_obj(db: Session) -> Credentials:
    settings = get_settings()
    refresh = token_store.get_refresh_token(db)
    if not refresh:
        raise AppError(
            "google_not_connected",
            "Подключите Google-аккаунт в настройках",
            status_code=503,
        )
    creds = Credentials(
        token=None,
        refresh_token=refresh,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=SCOPES,
    )
    try:
        creds.refresh(Request())
    except Exception as exc:
        token_store.mark_reauth_required(db, str(exc))
        raise AppError(
            "google_reauth_required",
            "Доступ к Google-аккаунту утрачен. "
            "Переподключите Google в настройках",
            status_code=502,
        ) from exc
    row = token_store.get_credentials(db)
    if row:
        row.last_refresh_at = utc_now()
        row.status = "active"
        db.commit()
    return creds


def revoke_token(db: Session) -> None:
    refresh = token_store.get_refresh_token(db)
    if refresh:
        try:
            with httpx.Client(timeout=15) as client:
                client.post(
                    "https://oauth2.googleapis.com/revoke",
                    data={"token": refresh},
                )
        except Exception:
            pass
    token_store.clear_credentials(db)


def get_setting(db: Session, key: str) -> str | None:
    row = db.get(AppSetting, key)
    return row.value if row else None


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
        row.updated_at = utc_now()
    db.commit()
