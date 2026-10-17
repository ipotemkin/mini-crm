"""Google Drive API helpers."""

from __future__ import annotations

from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import AppError
from app.export.errors import raise_google_error
from app.export.oauth import get_credentials_obj, get_setting, set_setting


def _service(db: Session):
    creds = get_credentials_obj(db)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def create_folder(db: Session, name: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    folder_name = name or settings.google_export_folder_name
    body = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    try:
        service = _service(db)
        created = (
            service.files()
            .create(
                body=body,
                fields="id,name,webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )
    except HttpError as exc:
        raise_google_error(exc)
        raise
    set_setting(db, "google_drive_folder_id", created["id"])
    set_setting(db, "google_drive_folder_name", created["name"])
    return created


def ensure_default_folder(db: Session) -> dict[str, Any]:
    folder_id = get_setting(db, "google_drive_folder_id")
    if folder_id:
        try:
            return get_folder(db, folder_id)
        except AppError:
            pass
    return create_folder(db)


def get_folder(db: Session, folder_id: str) -> dict[str, Any]:
    try:
        service = _service(db)
        meta = (
            service.files()
            .get(
                fileId=folder_id,
                fields=(
                    "id,name,mimeType,trashed,"
                    "capabilities/canAddChildren,webViewLink"
                ),
                supportsAllDrives=True,
            )
            .execute()
        )
    except HttpError as exc:
        raise_google_error(exc)
        raise
    if meta.get("mimeType") != "application/vnd.google-apps.folder":
        raise AppError(
            "google_folder_invalid",
            "Указанный объект не является папкой",
            status_code=502,
        )
    if meta.get("trashed"):
        raise AppError(
            "google_folder_invalid",
            "Папка удалена в корзину",
            status_code=502,
        )
    caps = meta.get("capabilities") or {}
    if caps.get("canAddChildren") is False:
        raise AppError(
            "google_folder_permission_denied",
            "Нет прав на добавление файлов в эту папку",
            status_code=502,
        )
    return meta


def create_spreadsheet(
    db: Session,
    name: str,
    folder_id: str,
    description: str,
) -> dict[str, Any]:
    body = {
        "name": name,
        "mimeType": "application/vnd.google-apps.spreadsheet",
        "parents": [folder_id],
        "description": description,
    }
    try:
        service = _service(db)
        return (
            service.files()
            .create(
                body=body,
                fields="id,name,webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )
    except HttpError as exc:
        raise_google_error(exc)
        raise


def trash_file(db: Session, file_id: str) -> None:
    try:
        service = _service(db)
        service.files().update(
            fileId=file_id,
            body={"trashed": True},
            supportsAllDrives=True,
        ).execute()
    except Exception:
        pass


def parse_folder_id(value: str) -> str:
    value = value.strip()
    marker = "/folders/"
    if marker in value:
        part = value.split(marker, 1)[1]
        return part.split("?")[0].split("/")[0]
    return value
