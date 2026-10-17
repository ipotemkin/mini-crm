"""Export orchestration: create Sheet file and write rows."""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.enums import DEAL_OPEN_STATUSES
from app.core.errors import AppError
from app.core.timeutils import utc_now
from app.export import columns, drive, sheets
from app.export.oauth import get_setting
from app.export.token_store import get_credentials
from app.models.deal import Deal
from app.models.settings import ExportLog
from app.models.task import Task
from app.schemas.client import ClientFilters
from app.schemas.deal import DealFilters
from app.schemas.order import OrderFilters
from app.schemas.task import TaskFilters
from app.services import clients as client_svc
from app.services import deals as deal_svc
from app.services import orders as order_svc
from app.services import search as search_svc
from app.services import tasks as task_svc


def _file_name(entity: str, scope_label: str | None = None) -> str:
    settings = get_settings()
    label = columns.ENTITY_LABELS.get(entity, entity)
    if scope_label:
        label = f"{label} {scope_label}"
    now = datetime.now(
        __import__("zoneinfo").ZoneInfo(settings.app_timezone)
    )
    try:
        return settings.export_file_name_template.format(
            entity=label,
            now=now,
        )
    except Exception:
        return f"{label} — {now:%Y-%m-%d %H-%M}"


def _collect_rows(
    db: Session,
    entity: str,
    filters: dict[str, Any],
) -> tuple[list[str], list[list], str]:
    if entity == "clients":
        f = ClientFilters(**filters)
        rows_db = client_svc.list_clients_all(db, f)
        data = []
        for c in rows_db:
            open_deals = db.scalar(
                select(func.count()).where(
                    Deal.client_id == c.id,
                    Deal.deleted_at.is_(None),
                    Deal.status.in_(
                        [s.value for s in DEAL_OPEN_STATUSES]
                    ),
                )
            ) or 0
            open_tasks = db.scalar(
                select(func.count()).where(
                    Task.client_id == c.id,
                    Task.deleted_at.is_(None),
                    Task.is_done.is_(False),
                )
            ) or 0
            data.append(columns.client_row(c, open_deals, open_tasks))
        return columns.CLIENT_HEADERS, data, "Клиенты"

    if entity == "deals":
        f = DealFilters(**filters)
        rows_db = deal_svc.list_deals_all(db, f)
        data = [columns.deal_row(d) for d in rows_db]
        return columns.DEAL_HEADERS, data, "Сделки"

    if entity == "orders":
        f = OrderFilters(**filters)
        rows_db = order_svc.list_orders_all(db, f)
        data = [columns.order_row(o) for o in rows_db]
        return columns.ORDER_HEADERS, data, "Заказы"

    if entity == "tasks":
        f = TaskFilters(**filters)
        rows_db = task_svc.list_tasks_all(db, f)
        data = [columns.task_row(t) for t in rows_db]
        return columns.TASK_HEADERS, data, "Задачи"

    if entity == "search":
        q = filters.get("q") or ""
        result = search_svc.global_search(
            db,
            q,
            limit=int(filters.get("limit") or 50),
            include_archived=True,
        )
        data = []
        for c in result["clients"]:
            data.append(
                [
                    "Клиент",
                    c["id"],
                    c["name"],
                    str(c["status"]),
                    "",
                    str(c["updated_at"]),
                ]
            )
        for d in result["deals"]:
            data.append(
                [
                    "Сделка",
                    d["id"],
                    d["title"],
                    str(d["status"]),
                    d.get("client_id") or "",
                    str(d["updated_at"]),
                ]
            )
        return columns.SEARCH_HEADERS, data, "Поиск"

    raise AppError("bad_request", f"Неизвестная сущность: {entity}")


def preview_export(
    db: Session,
    entity: str,
    filters: dict[str, Any],
) -> dict[str, Any]:
    settings = get_settings()
    _, rows, sheet_title = _collect_rows(db, entity, filters)
    folder_name = get_setting(db, "google_drive_folder_name") or (
        settings.google_export_folder_name
    )
    return {
        "rows": len(rows),
        "file_name": _file_name(entity),
        "folder_name": folder_name,
        "sheet_title": sheet_title,
        "max_rows": settings.export_max_rows,
    }


def run_export(
    db: Session,
    entity: str,
    filters: dict[str, Any],
    scope_label: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    started = time.monotonic()
    if not settings.google_configured:
        raise AppError(
            "export_not_configured",
            "Экспорт не настроен администратором",
            status_code=503,
        )
    creds = get_credentials(db)
    if creds is None or creds.status == "reauth_required":
        raise AppError(
            "google_not_connected"
            if creds is None
            else "google_reauth_required",
            "Подключите Google-аккаунт в настройках"
            if creds is None
            else "Переподключите Google в настройках",
            status_code=503 if creds is None else 502,
        )
    folder_id = get_setting(db, "google_drive_folder_id")
    if not folder_id:
        raise AppError(
            "google_folder_not_set",
            "Выберите папку для выгрузок в настройках",
            status_code=503,
        )
    folder = drive.get_folder(db, folder_id)
    headers, rows, sheet_title = _collect_rows(db, entity, filters)
    if len(rows) > settings.export_max_rows:
        raise AppError(
            "export_too_large",
            f"Слишком много строк ({len(rows)} > лимит "
            f"{settings.export_max_rows}): сузьте фильтры",
            status_code=422,
        )
    file_name = _file_name(entity, scope_label)
    description = (
        f"Выгрузка {sheet_title}; строк: {len(rows)}; "
        f"фильтры: {json.dumps(filters, ensure_ascii=False, default=str)}"
    )
    created = None
    try:
        created = drive.create_spreadsheet(
            db,
            file_name,
            folder_id,
            description,
        )
        sheets.write_sheet(
            db,
            created["id"],
            sheet_title,
            headers,
            rows,
            note=description,
        )
    except Exception as exc:
        if created and created.get("id"):
            drive.trash_file(db, created["id"])
        _log(
            db,
            entity,
            None,
            file_name,
            None,
            folder_id,
            len(rows),
            "failed",
            getattr(exc, "code", "export_failed"),
            filters,
            int((time.monotonic() - started) * 1000),
        )
        raise

    duration = int((time.monotonic() - started) * 1000)
    result = {
        "file_id": created["id"],
        "file_name": created.get("name", file_name),
        "url": created.get("webViewLink"),
        "folder_id": folder_id,
        "folder_name": folder.get("name"),
        "folder_url": folder.get("webViewLink")
        or f"https://drive.google.com/drive/folders/{folder_id}",
        "rows": len(rows),
    }
    _log(
        db,
        entity,
        result["file_id"],
        result["file_name"],
        result["url"],
        folder_id,
        len(rows),
        "success",
        None,
        filters,
        duration,
    )
    return result


def _log(
    db: Session,
    entity: str,
    file_id: str | None,
    file_name: str | None,
    file_url: str | None,
    folder_id: str | None,
    rows: int | None,
    status: str,
    error_code: str | None,
    filters: dict,
    duration_ms: int,
) -> None:
    db.add(
        ExportLog(
            entity=entity,
            file_id=file_id,
            file_name=file_name,
            file_url=file_url,
            folder_id=folder_id,
            rows=rows,
            status=status,
            error_code=error_code,
            filters=json.dumps(
                filters,
                ensure_ascii=False,
                default=str,
            ),
            duration_ms=duration_ms,
            created_at=utc_now(),
        )
    )
    # Keep last 1000
    ids = db.scalars(
        select(ExportLog.id).order_by(ExportLog.id.desc())
    ).all()
    if len(ids) > 1000:
        for old_id in ids[1000:]:
            row = db.get(ExportLog, old_id)
            if row:
                db.delete(row)
    db.commit()


def export_status(db: Session) -> dict[str, Any]:
    settings = get_settings()
    creds = get_credentials(db)
    folder_id = get_setting(db, "google_drive_folder_id")
    folder_name = get_setting(db, "google_drive_folder_name")
    return {
        "configured": settings.google_configured,
        "missing": _missing_env(settings),
        "connected": creds is not None and bool(
            creds.refresh_token_encrypted
        ),
        "account_email": creds.account_email if creds else None,
        "status": creds.status if creds else "disconnected",
        "last_error": creds.last_error if creds else None,
        "last_error_at": creds.last_error_at if creds else None,
        "last_refresh_at": creds.last_refresh_at if creds else None,
        "folder_id": folder_id,
        "folder_name": folder_name,
        "folder_url": (
            f"https://drive.google.com/drive/folders/{folder_id}"
            if folder_id
            else None
        ),
        "picker_ready": bool(
            settings.google_picker_api_key
            and settings.google_cloud_project_number
        ),
    }


def _missing_env(settings) -> list[str]:
    missing = []
    for name, value in [
        ("GOOGLE_OAUTH_CLIENT_ID", settings.google_oauth_client_id),
        ("GOOGLE_OAUTH_CLIENT_SECRET", settings.google_oauth_client_secret),
        (
            "GOOGLE_TOKEN_ENCRYPTION_KEY",
            settings.google_token_encryption_key,
        ),
    ]:
        if not value:
            missing.append(name)
    return missing
