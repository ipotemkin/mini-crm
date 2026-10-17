"""Tasks API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from app.api.deps import AuthUser, Csrf, DbSession
from app.core.errors import AppError
from app.core.enums import TaskType
from app.schemas.task import TaskCreate, TaskFilters, TaskUpdate
from app.services import tasks as svc

router = APIRouter(tags=["tasks"])


def _raise(exc: AppError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail=exc.as_http_detail(),
    )


@router.get("/tasks")
def list_tasks(
    db: DbSession,
    _user: AuthUser,
    q: str | None = None,
    view: str = "active",
    due_state: str | None = None,
    task_type: TaskType | None = None,
    client_id: int | None = None,
    deal_id: int | None = None,
    due_from: str | None = None,
    due_to: str | None = None,
    sort: str = "due_at",
    order: str = "asc",
    page: int = 1,
    page_size: int = 25,
):
    try:
        filters = TaskFilters(
            q=q,
            view=view,  # type: ignore[arg-type]
            due_state=due_state,  # type: ignore[arg-type]
            task_type=task_type,
            client_id=client_id,
            deal_id=deal_id,
            due_from=due_from,
            due_to=due_to,
            sort=sort,
            order=order,  # type: ignore[arg-type]
            page=page,
            page_size=page_size,
        )
        return svc.list_tasks(db, filters)
    except AppError as exc:
        _raise(exc)


@router.post("/tasks", status_code=201)
def create_task(
    body: TaskCreate,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
):
    try:
        return svc.create_task(db, body)
    except AppError as exc:
        _raise(exc)


@router.get("/tasks/{task_id}")
def get_task(task_id: int, db: DbSession, _user: AuthUser):
    try:
        return svc.get_task(db, task_id)
    except AppError as exc:
        _raise(exc)


@router.patch("/tasks/{task_id}")
def patch_task(
    task_id: int,
    body: TaskUpdate,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
):
    try:
        return svc.update_task(db, task_id, body)
    except AppError as exc:
        _raise(exc)


@router.post("/tasks/{task_id}/complete")
def complete(task_id: int, db: DbSession, _user: AuthUser, _csrf: Csrf):
    try:
        return svc.complete_task(db, task_id)
    except AppError as exc:
        _raise(exc)


@router.post("/tasks/{task_id}/reopen")
def reopen(task_id: int, db: DbSession, _user: AuthUser, _csrf: Csrf):
    try:
        return svc.reopen_task(db, task_id)
    except AppError as exc:
        _raise(exc)


@router.post("/tasks/{task_id}/snooze/{mode}")
def snooze(
    task_id: int,
    mode: str,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
):
    try:
        return svc.snooze_task(db, task_id, mode)
    except AppError as exc:
        _raise(exc)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
):
    try:
        svc.delete_task(db, task_id)
    except AppError as exc:
        _raise(exc)
    return Response(status_code=204)


@router.get("/reminders/summary")
def reminders(db: DbSession, _user: AuthUser):
    return svc.reminder_summary(db)
