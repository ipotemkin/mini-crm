"""Export and Google settings API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.api.deps import AuthUser, Csrf, DbSession
from app.config import get_settings
from app.core.errors import AppError
from app.export import drive, exporter, oauth, token_store
from app.export.oauth import get_credentials_obj
from app.models.settings import ExportLog
from app.schemas.common import Page

router = APIRouter(tags=["exports"])


def _raise(exc: AppError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail=exc.as_http_detail(),
    )


class FolderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folder_id: str | None = None
    folder_url: str | None = None


class FolderCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None


@router.get("/exports/status")
def status(db: DbSession, _user: AuthUser):
    return exporter.export_status(db)


@router.post("/exports/check")
def check(db: DbSession, _user: AuthUser, _csrf: Csrf):
    try:
        folder_id = oauth.get_setting(db, "google_drive_folder_id")
        if not folder_id:
            raise AppError(
                "google_folder_not_set",
                "Выберите папку для выгрузок в настройках",
                status_code=503,
            )
        folder = drive.get_folder(db, folder_id)
        creds = token_store.get_credentials(db)
        return {
            "ok": True,
            "account_email": creds.account_email if creds else None,
            "folder_name": folder.get("name"),
            "folder_url": folder.get("webViewLink"),
        }
    except AppError as exc:
        _raise(exc)


@router.get("/exports/preview/{entity}")
def preview(
    entity: str,
    db: DbSession,
    _user: AuthUser,
    q: str | None = None,
):
    try:
        return exporter.preview_export(db, entity, {"q": q} if q else {})
    except AppError as exc:
        _raise(exc)


@router.post("/exports/{entity}", status_code=201)
def export_entity(
    entity: str,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
    body: dict[str, Any] | None = None,
):
    try:
        return exporter.run_export(db, entity, body or {})
    except AppError as exc:
        _raise(exc)


@router.get("/exports")
def export_log(
    db: DbSession,
    _user: AuthUser,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
):
    stmt = select(ExportLog).order_by(ExportLog.id.desc())
    if status:
        stmt = stmt.where(ExportLog.status == status)
    rows = db.scalars(stmt).all()
    total = len(rows)
    page_size = min(page_size, 100)
    pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, pages) if total else 1
    chunk = rows[(page - 1) * page_size : page * page_size]
    items = [
        {
            "id": r.id,
            "entity": r.entity,
            "file_id": r.file_id,
            "file_name": r.file_name,
            "file_url": r.file_url,
            "folder_id": r.folder_id,
            "rows": r.rows,
            "status": r.status,
            "error_code": r.error_code,
            "duration_ms": r.duration_ms,
            "created_at": r.created_at,
        }
        for r in chunk
    ]
    return Page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages if total else 1,
    )


@router.post("/settings/google/disconnect")
def disconnect(db: DbSession, _user: AuthUser, _csrf: Csrf):
    oauth.revoke_token(db)
    return {"ok": True}


@router.put("/settings/google/folder")
def set_folder(
    body: FolderBody,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
):
    try:
        raw = body.folder_id or body.folder_url
        if not raw:
            raise AppError("bad_request", "Укажите ID или ссылку папки")
        folder_id = drive.parse_folder_id(raw)
        meta = drive.get_folder(db, folder_id)
        oauth.set_setting(db, "google_drive_folder_id", meta["id"])
        oauth.set_setting(db, "google_drive_folder_name", meta["name"])
        return {
            "folder_id": meta["id"],
            "folder_name": meta["name"],
            "folder_url": meta.get("webViewLink"),
        }
    except AppError as exc:
        _raise(exc)


@router.post("/settings/google/folder/create")
def create_folder(
    body: FolderCreateBody,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
):
    try:
        created = drive.create_folder(db, body.name)
        return {
            "folder_id": created["id"],
            "folder_name": created["name"],
            "folder_url": created.get("webViewLink"),
        }
    except AppError as exc:
        _raise(exc)


@router.get("/settings/google/picker-config")
def picker_config(db: DbSession, _user: AuthUser):
    settings = get_settings()
    if not settings.google_configured:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "export_not_configured",
                "message": "Экспорт не настроен",
            },
        )
    try:
        creds = get_credentials_obj(db)
    except AppError as exc:
        _raise(exc)
        return
    return {
        "access_token": creds.token,
        "api_key": settings.google_picker_api_key,
        "app_id": settings.google_cloud_project_number,
        "client_id": settings.google_oauth_client_id,
    }
