"""Encrypted refresh token storage (Fernet)."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import AppError
from app.core.timeutils import utc_now
from app.models.settings import GoogleOAuthCredential


def _fernet() -> Fernet:
    key = get_settings().google_token_encryption_key
    if not key:
        raise AppError(
            "export_not_configured",
            "Экспорт не настроен администратором",
            status_code=503,
        )
    return Fernet(key.encode("utf-8"))


def encrypt_token(token: str) -> bytes:
    return _fernet().encrypt(token.encode("utf-8"))


def decrypt_token(blob: bytes) -> str:
    try:
        return _fernet().decrypt(blob).decode("utf-8")
    except InvalidToken as exc:
        raise AppError(
            "google_reauth_required",
            "Не удалось расшифровать токен Google. "
            "Переподключите аккаунт",
            status_code=502,
        ) from exc


def get_credentials(db: Session) -> GoogleOAuthCredential | None:
    return db.get(GoogleOAuthCredential, 1)


def save_credentials(
    db: Session,
    *,
    email: str,
    scopes: str,
    refresh_token: str,
) -> GoogleOAuthCredential:
    row = get_credentials(db)
    if row is None:
        row = GoogleOAuthCredential(id=1)
        db.add(row)
    row.account_email = email
    row.scopes = scopes
    row.refresh_token_encrypted = encrypt_token(refresh_token)
    row.status = "active"
    row.connected_at = utc_now()
    row.last_refresh_at = utc_now()
    row.last_error = None
    row.last_error_at = None
    db.commit()
    db.refresh(row)
    return row


def mark_reauth_required(db: Session, error: str) -> None:
    row = get_credentials(db)
    if row is None:
        return
    row.status = "reauth_required"
    row.last_error = error
    row.last_error_at = utc_now()
    db.commit()


def clear_credentials(db: Session) -> None:
    row = get_credentials(db)
    if row is None:
        return
    db.delete(row)
    db.commit()


def get_refresh_token(db: Session) -> str | None:
    row = get_credentials(db)
    if row is None or not row.refresh_token_encrypted:
        return None
    return decrypt_token(row.refresh_token_encrypted)
