"""Tasks HTML pages."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.enums import TaskType
from app.core.errors import AppError
from app.db import get_db
from app.schemas.task import TaskCreate, TaskFilters, TaskUpdate
from app.services import tasks as svc
from app.web.deps import render, require_web_user

router = APIRouter(prefix="/tasks", tags=["web-tasks"])


@router.get("")
def list_page(
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
    q: str | None = None,
    view: str = "active",
    task_type: str | None = None,
    client_id: int | None = None,
    deal_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
):
    filters = TaskFilters(
        q=q,
        view=view,  # type: ignore[arg-type]
        task_type=TaskType(task_type) if task_type else None,
        client_id=client_id,
        deal_id=deal_id,
        page=page,
        page_size=page_size,
    )
    result = svc.list_tasks(db, filters)
    grouped: dict[str, list] = {
        "overdue": [],
        "today": [],
        "upcoming": [],
        "no_due": [],
        "done": [],
    }
    for item in result.items:
        grouped.setdefault(item.due_state, []).append(item)
    return render(
        request,
        "tasks/list.html",
        {
            "page_data": result,
            "filters": filters,
            "grouped": grouped,
            "types": list(TaskType),
        },
    )


@router.get("/new")
def new_form(
    request: Request,
    client_id: int | None = None,
    deal_id: int | None = None,
    _user=Depends(require_web_user),
):
    return render(
        request,
        "tasks/form.html",
        {
            "task": None,
            "client_id": client_id,
            "deal_id": deal_id,
            "types": list(TaskType),
        },
    )


@router.post("/new")
def create(
    title: str = Form(...),
    task_type: str = Form("todo"),
    due_date: str | None = Form(None),
    description: str | None = Form(None),
    client_id: str | None = Form(None),
    deal_id: str | None = Form(None),
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    from datetime import date as date_cls

    created = svc.create_task(
        db,
        TaskCreate(
            title=title,
            task_type=TaskType(task_type),
            due_date=(
                date_cls.fromisoformat(due_date) if due_date else None
            ),
            description=description or None,
            client_id=int(client_id) if client_id else None,
            deal_id=int(deal_id) if deal_id else None,
        ),
    )
    return RedirectResponse(
        f"/tasks?flash=Задача+создана&view=active",
        status_code=303,
    )


@router.get("/{task_id}/edit")
def edit_form(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    try:
        task = svc.get_task(db, task_id)
    except AppError:
        return render(request, "errors/404.html", status_code=404)
    return render(
        request,
        "tasks/form.html",
        {"task": task, "types": list(TaskType)},
    )


@router.post("/{task_id}/edit")
def edit_submit(
    task_id: int,
    title: str = Form(...),
    task_type: str = Form("todo"),
    due_date: str | None = Form(None),
    description: str | None = Form(None),
    client_id: str | None = Form(None),
    deal_id: str | None = Form(None),
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    from datetime import date as date_cls

    svc.update_task(
        db,
        task_id,
        TaskUpdate(
            title=title,
            task_type=TaskType(task_type),
            due_date=(
                date_cls.fromisoformat(due_date) if due_date else None
            ),
            clear_due=not due_date,
            description=description or None,
            client_id=int(client_id) if client_id else None,
            deal_id=int(deal_id) if deal_id else None,
        ),
    )
    return RedirectResponse("/tasks?flash=Сохранено", status_code=303)


@router.post("/{task_id}/toggle")
def toggle(
    task_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    task = svc.get_task(db, task_id)
    if task.is_done:
        svc.reopen_task(db, task_id)
    else:
        svc.complete_task(db, task_id)
    return RedirectResponse("/tasks", status_code=303)


@router.post("/{task_id}/snooze/{mode}")
def snooze(
    task_id: int,
    mode: str,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    svc.snooze_task(db, task_id, mode)
    return RedirectResponse("/tasks", status_code=303)


@router.post("/{task_id}/delete")
def delete(
    task_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    svc.delete_task(db, task_id)
    return RedirectResponse(
        "/tasks?flash=Задача+удалена",
        status_code=303,
    )
