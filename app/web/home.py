"""Dashboard «Сегодня»."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.enums import DEAL_OPEN_STATUSES
from app.db import get_db
from app.schemas.deal import DealFilters
from app.schemas.task import TaskCreate
from app.services import deals as deal_svc
from app.services import tasks as task_svc
from app.web.deps import render, require_web_user

router = APIRouter(tags=["web-home"])


@router.get("/")
def today(
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    groups = task_svc.dashboard_tasks(db)
    open_deals = deal_svc.list_deals(
        db,
        DealFilters(group="open", page_size=5, sort="updated_at"),
    )
    total_open = deal_svc.sum_amounts(
        db,
        DealFilters(group="open", page_size=1),
    )
    return render(
        request,
        "home.html",
        {
            "overdue": groups["overdue"],
            "today_tasks": groups["today"],
            "upcoming": groups["upcoming"],
            "open_deals": open_deals.items,
            "open_deals_sum": total_open,
        },
    )


@router.post("/tasks/quick")
def quick_task(
    request: Request,
    title: str = Form(...),
    due_date: str | None = Form(None),
    client_id: int | None = Form(None),
    deal_id: int | None = Form(None),
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    from datetime import date as date_cls

    due = date_cls.fromisoformat(due_date) if due_date else None
    task_svc.create_task(
        db,
        TaskCreate(
            title=title,
            due_date=due,
            client_id=client_id or None,
            deal_id=deal_id or None,
        ),
    )
    referer = request.headers.get("referer") or "/tasks"
    return RedirectResponse(referer, status_code=303)
