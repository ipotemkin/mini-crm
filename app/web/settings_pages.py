"""Settings page."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import __version__
from app.config import get_settings
from app.core.errors import AppError
from app.db import get_db
from app.export import drive, exporter, oauth
from app.models.settings import ExportLog
from app.web.deps import render, require_web_user

router = APIRouter(tags=["web-settings"])


@router.get("/settings")
def settings_page(
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    status = exporter.export_status(db)
    logs = db.scalars(
        select(ExportLog).order_by(ExportLog.id.desc()).limit(20)
    ).all()
    backup_dir = Path(get_settings().backup_dir)
    last_backup = None
    if backup_dir.exists():
        files = sorted(backup_dir.glob("crm-*.sqlite3.gz"), reverse=True)
        if files:
            last_backup = files[0].name
    return render(
        request,
        "settings/index.html",
        {
            "status": status,
            "logs": logs,
            "version": __version__,
            "last_backup": last_backup,
        },
    )


@router.post("/settings/google/folder")
def save_folder(
    folder_url: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    try:
        folder_id = drive.parse_folder_id(folder_url)
        meta = drive.get_folder(db, folder_id)
        oauth.set_setting(db, "google_drive_folder_id", meta["id"])
        oauth.set_setting(db, "google_drive_folder_name", meta["name"])
        return RedirectResponse(
            "/settings?flash=Папка+сохранена",
            status_code=303,
        )
    except AppError as exc:
        return RedirectResponse(
            f"/settings?error={exc.message}",
            status_code=303,
        )


@router.post("/settings/google/folder/create")
def create_folder(
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    try:
        drive.create_folder(db)
        return RedirectResponse(
            "/settings?flash=Папка+создана",
            status_code=303,
        )
    except AppError as exc:
        return RedirectResponse(
            f"/settings?error={exc.message}",
            status_code=303,
        )


@router.post("/settings/google/disconnect")
def disconnect(
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    oauth.revoke_token(db)
    return RedirectResponse(
        "/settings?flash=Google+отключён",
        status_code=303,
    )


@router.post("/settings/google/check")
def check(
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    try:
        folder_id = oauth.get_setting(db, "google_drive_folder_id")
        if not folder_id:
            raise AppError(
                "google_folder_not_set",
                "Папка не задана",
                status_code=503,
            )
        drive.get_folder(db, folder_id)
        return RedirectResponse(
            "/settings?flash=Подключение+в+порядке",
            status_code=303,
        )
    except AppError as exc:
        return RedirectResponse(
            f"/settings?error={exc.message}",
            status_code=303,
        )


@router.post("/exports/{entity}")
def export_from_ui(
    entity: str,
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    try:
        filters = dict(request.query_params)
        result = exporter.run_export(db, entity, filters)
        return RedirectResponse(
            f"{request.headers.get('referer', '/')}?"
            f"flash=Создан+файл+{result['file_name']}"
            f"&export_url={result['url']}",
            status_code=303,
        )
    except AppError as exc:
        return RedirectResponse(
            f"/settings?error={exc.message}"
            if "google" in exc.code or "export" in exc.code
            else f"{request.headers.get('referer', '/')}?error={exc.message}",
            status_code=303,
        )
