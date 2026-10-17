"""Orders HTML pages."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.enums import OrderStatus
from app.core.errors import AppError
from app.db import get_db
from app.schemas.order import OrderCreate, OrderFilters, OrderUpdate
from app.services import orders as svc
from app.web.deps import render, require_web_user

router = APIRouter(prefix="/orders", tags=["web-orders"])


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
    status: list[str] | None = Query(default=None),
    client_id: int | None = None,
    deal_id: int | None = None,
    sort: str = "order_date",
    order: str = "desc",
    page: int = 1,
    page_size: int = 25,
):
    statuses = [OrderStatus(s) for s in (status or [])]
    filters = OrderFilters(
        q=q,
        status=statuses or None,
        client_id=client_id,
        deal_id=deal_id,
        sort=sort,
        order=order,  # type: ignore[arg-type]
        page=page,
        page_size=page_size,
    )
    result = svc.list_orders(db, filters)
    total_amount = svc.sum_amounts(db, filters)
    return render(
        request,
        "orders/list.html",
        {
            "page_data": result,
            "filters": filters,
            "statuses": list(OrderStatus),
            "total_amount": total_amount,
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
        "orders/form.html",
        {
            "order": None,
            "client_id": client_id,
            "deal_id": deal_id,
            "statuses": list(OrderStatus),
        },
    )


@router.post("/new")
def create(
    title: str = Form(...),
    client_id: str | None = Form(None),
    deal_id: str | None = Form(None),
    amount: str | None = Form(None),
    order_date: str | None = Form(None),
    due_date: str | None = Form(None),
    comment: str | None = Form(None),
    status: str = Form("new"),
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    from datetime import date as date_cls

    created = svc.create_order(
        db,
        OrderCreate(
            title=title,
            client_id=int(client_id) if client_id else None,
            deal_id=int(deal_id) if deal_id else None,
            amount=_parse_amount(amount),
            order_date=(
                date_cls.fromisoformat(order_date) if order_date else None
            ),
            due_date=(
                date_cls.fromisoformat(due_date) if due_date else None
            ),
            comment=comment or None,
            status=OrderStatus(status),
        ),
    )
    return RedirectResponse(
        f"/orders/{created.id}?flash=Заказ+создан",
        status_code=303,
    )


@router.get("/{order_id}")
def detail(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    try:
        order = svc.get_order(db, order_id)
    except AppError:
        return render(request, "errors/404.html", status_code=404)
    return render(
        request,
        "orders/detail.html",
        {"order": order, "statuses": list(OrderStatus)},
    )


@router.get("/{order_id}/edit")
def edit_form(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    try:
        order = svc.get_order(db, order_id)
    except AppError:
        return render(request, "errors/404.html", status_code=404)
    return render(
        request,
        "orders/form.html",
        {"order": order, "statuses": list(OrderStatus)},
    )


@router.post("/{order_id}/edit")
def edit_submit(
    order_id: int,
    title: str = Form(...),
    client_id: str | None = Form(None),
    deal_id: str | None = Form(None),
    amount: str | None = Form(None),
    order_date: str | None = Form(None),
    due_date: str | None = Form(None),
    comment: str | None = Form(None),
    status: str = Form("new"),
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    from datetime import date as date_cls

    svc.update_order(
        db,
        order_id,
        OrderUpdate(
            title=title,
            client_id=int(client_id) if client_id else None,
            deal_id=int(deal_id) if deal_id else None,
            amount=_parse_amount(amount),
            order_date=(
                date_cls.fromisoformat(order_date) if order_date else None
            ),
            due_date=(
                date_cls.fromisoformat(due_date) if due_date else None
            ),
            comment=comment or None,
            status=OrderStatus(status),
        ),
    )
    return RedirectResponse(
        f"/orders/{order_id}?flash=Сохранено",
        status_code=303,
    )


@router.post("/{order_id}/delete")
def delete(
    order_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    svc.delete_order(db, order_id)
    return RedirectResponse(
        "/orders?flash=Заказ+удалён",
        status_code=303,
    )
