"""Deals HTML pages."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.enums import DealStatus
from app.core.errors import AppError
from app.db import get_db
from app.schemas.deal import DealCreate, DealFilters, DealStatusUpdate, DealUpdate
from app.schemas.order import OrderFilters
from app.schemas.task import TaskFilters
from app.services import deals as svc
from app.services import orders as order_svc
from app.services import tasks as task_svc
from app.web.deps import render, require_web_user

router = APIRouter(prefix="/deals", tags=["web-deals"])


def _parse_amount(raw: str | None) -> Decimal | None:
    if not raw:
        return None
    try:
        return Decimal(raw.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return None


@router.get("")
def list_page(
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
    q: str | None = None,
    group: str = "open",
    status: list[str] | None = Query(default=None),
    client_id: int | None = None,
    no_client: bool = False,
    sort: str = "updated_at",
    order: str = "desc",
    page: int = 1,
    page_size: int = 25,
):
    statuses = [DealStatus(s) for s in (status or [])]
    filters = DealFilters(
        q=q,
        group=group,  # type: ignore[arg-type]
        status=statuses or None,
        client_id=client_id,
        no_client=no_client,
        sort=sort,
        order=order,  # type: ignore[arg-type]
        page=page,
        page_size=page_size,
    )
    result = svc.list_deals(db, filters)
    total_amount = svc.sum_amounts(db, filters)
    return render(
        request,
        "deals/list.html",
        {
            "page_data": result,
            "filters": filters,
            "statuses": list(DealStatus),
            "total_amount": total_amount,
        },
    )


@router.get("/new")
def new_form(
    request: Request,
    client_id: int | None = None,
    _user=Depends(require_web_user),
):
    return render(
        request,
        "deals/form.html",
        {
            "deal": None,
            "client_id": client_id,
            "statuses": list(DealStatus),
        },
    )


@router.post("/new")
def create(
    title: str = Form(...),
    client_id: str | None = Form(None),
    amount: str | None = Form(None),
    expected_close_date: str | None = Form(None),
    description: str | None = Form(None),
    status: str = Form("new"),
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    from datetime import date as date_cls

    cid = int(client_id) if client_id else None
    created = svc.create_deal(
        db,
        DealCreate(
            title=title,
            client_id=cid,
            amount=_parse_amount(amount),
            expected_close_date=(
                date_cls.fromisoformat(expected_close_date)
                if expected_close_date
                else None
            ),
            description=description or None,
            status=DealStatus(status),
        ),
    )
    return RedirectResponse(
        f"/deals/{created.id}?flash=Сделка+создана",
        status_code=303,
    )


@router.get("/{deal_id}")
def detail(
    deal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    try:
        deal = svc.get_deal(db, deal_id)
    except AppError:
        return render(request, "errors/404.html", status_code=404)
    orders = order_svc.list_orders(
        db,
        OrderFilters(deal_id=deal_id, page_size=50),
    )
    tasks = task_svc.list_tasks(
        db,
        TaskFilters(deal_id=deal_id, view="all", page_size=100),
    )
    impact = svc.delete_impact(db, deal_id)
    return render(
        request,
        "deals/detail.html",
        {
            "deal": deal,
            "orders": orders.items,
            "tasks": tasks.items,
            "impact": impact,
            "statuses": list(DealStatus),
        },
    )


@router.get("/{deal_id}/edit")
def edit_form(
    deal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    try:
        deal = svc.get_deal(db, deal_id)
    except AppError:
        return render(request, "errors/404.html", status_code=404)
    return render(
        request,
        "deals/form.html",
        {"deal": deal, "statuses": list(DealStatus)},
    )


@router.post("/{deal_id}/edit")
def edit_submit(
    deal_id: int,
    title: str = Form(...),
    client_id: str | None = Form(None),
    amount: str | None = Form(None),
    expected_close_date: str | None = Form(None),
    description: str | None = Form(None),
    lost_reason: str | None = Form(None),
    status: str = Form("new"),
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    from datetime import date as date_cls

    svc.update_deal(
        db,
        deal_id,
        DealUpdate(
            title=title,
            client_id=int(client_id) if client_id else None,
            amount=_parse_amount(amount),
            expected_close_date=(
                date_cls.fromisoformat(expected_close_date)
                if expected_close_date
                else None
            ),
            description=description or None,
            lost_reason=lost_reason or None,
            status=DealStatus(status),
        ),
    )
    return RedirectResponse(
        f"/deals/{deal_id}?flash=Сохранено",
        status_code=303,
    )


@router.post("/{deal_id}/status")
def change_status(
    deal_id: int,
    status: str = Form(...),
    lost_reason: str | None = Form(None),
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    result = svc.set_deal_status(
        db,
        deal_id,
        DealStatusUpdate(
            status=DealStatus(status),
            lost_reason=lost_reason or None,
        ),
    )
    flash = "Статус+обновлён"
    if result.status == DealStatus.WON:
        flash = "Статус+обновлён.+Создать+заказ%3F"
    return RedirectResponse(
        f"/deals/{deal_id}?flash={flash}",
        status_code=303,
    )


@router.post("/{deal_id}/attach")
def attach(
    deal_id: int,
    client_id: int = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    svc.attach_client(db, deal_id, client_id)
    return RedirectResponse(
        f"/deals/{deal_id}?flash=Клиент+прикреплён",
        status_code=303,
    )


@router.post("/{deal_id}/detach")
def detach(
    deal_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    svc.detach_client(db, deal_id)
    return RedirectResponse(
        f"/deals/{deal_id}?flash=Клиент+откреплён",
        status_code=303,
    )


@router.post("/{deal_id}/delete")
def delete(
    deal_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    svc.delete_deal(db, deal_id)
    return RedirectResponse(
        "/deals?flash=Сделка+удалена",
        status_code=303,
    )
