"""Deals API."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Response

from app.api.deps import AuthUser, Csrf, DbSession
from app.core.errors import AppError
from app.core.enums import DealStatus
from app.core.money import from_kopecks
from app.schemas.deal import (
    DealClientUpdate,
    DealCreate,
    DealFilters,
    DealStatusUpdate,
    DealUpdate,
)
from app.schemas.order import OrderCreate, OrderFilters
from app.schemas.task import TaskFilters
from app.services import deals as svc
from app.services import orders as order_svc
from app.services import tasks as task_svc

router = APIRouter(prefix="/deals", tags=["deals"])


def _raise(exc: AppError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail=exc.as_http_detail(),
    )


@router.get("")
def list_deals(
    db: DbSession,
    _user: AuthUser,
    q: str | None = None,
    status: list[DealStatus] | None = Query(default=None),
    group: str = "open",
    client_id: int | None = None,
    no_client: bool = False,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    close_from: str | None = None,
    close_to: str | None = None,
    sort: str = "updated_at",
    order: str = "desc",
    page: int = 1,
    page_size: int = 25,
):
    try:
        filters = DealFilters(
            q=q,
            status=status,
            group=group,  # type: ignore[arg-type]
            client_id=client_id,
            no_client=no_client,
            amount_min=amount_min,
            amount_max=amount_max,
            close_from=close_from,
            close_to=close_to,
            sort=sort,
            order=order,  # type: ignore[arg-type]
            page=page,
            page_size=page_size,
        )
        page_data = svc.list_deals(db, filters)
        total_amount = from_kopecks(svc.sum_amounts(db, filters))
        return {**page_data.model_dump(), "total_amount": total_amount}
    except AppError as exc:
        _raise(exc)


@router.post("", status_code=201)
def create_deal(
    body: DealCreate,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
):
    try:
        return svc.create_deal(db, body)
    except AppError as exc:
        _raise(exc)


@router.get("/lookup")
def lookup(db: DbSession, _user: AuthUser, q: str = "", limit: int = 10):
    return svc.lookup_deals(db, q, limit)


@router.get("/{deal_id}")
def get_deal(deal_id: int, db: DbSession, _user: AuthUser):
    try:
        return svc.get_deal(db, deal_id)
    except AppError as exc:
        _raise(exc)


@router.patch("/{deal_id}")
def patch_deal(
    deal_id: int,
    body: DealUpdate,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
):
    try:
        return svc.update_deal(db, deal_id, body)
    except AppError as exc:
        _raise(exc)


@router.post("/{deal_id}/status")
def set_status(
    deal_id: int,
    body: DealStatusUpdate,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
):
    try:
        return svc.set_deal_status(db, deal_id, body)
    except AppError as exc:
        _raise(exc)


@router.put("/{deal_id}/client")
def attach(
    deal_id: int,
    body: DealClientUpdate,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
):
    try:
        return svc.attach_client(db, deal_id, body.client_id)
    except AppError as exc:
        _raise(exc)


@router.delete("/{deal_id}/client")
def detach(deal_id: int, db: DbSession, _user: AuthUser, _csrf: Csrf):
    try:
        return svc.detach_client(db, deal_id)
    except AppError as exc:
        _raise(exc)


@router.delete("/{deal_id}", status_code=204)
def delete_deal(
    deal_id: int,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
):
    try:
        svc.delete_deal(db, deal_id)
    except AppError as exc:
        _raise(exc)
    return Response(status_code=204)


@router.get("/{deal_id}/orders")
def deal_orders(deal_id: int, db: DbSession, _user: AuthUser):
    svc.get_deal(db, deal_id)
    return order_svc.list_orders(
        db,
        OrderFilters(deal_id=deal_id, page_size=100),
    )


@router.get("/{deal_id}/tasks")
def deal_tasks(
    deal_id: int,
    db: DbSession,
    _user: AuthUser,
    is_done: bool | None = None,
):
    svc.get_deal(db, deal_id)
    view = "all"
    if is_done is True:
        view = "done"
    elif is_done is False:
        view = "active"
    return task_svc.list_tasks(
        db,
        TaskFilters(deal_id=deal_id, view=view, page_size=100),
    )


@router.post("/{deal_id}/orders", status_code=201)
def create_order_from_deal(
    deal_id: int,
    body: OrderCreate,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
):
    try:
        deal = svc.get_deal(db, deal_id)
        payload = body.model_copy(
            update={
                "deal_id": deal_id,
                "client_id": body.client_id or deal.client_id,
                "amount": body.amount
                if body.amount is not None
                else deal.amount,
                "title": body.title or deal.title,
            }
        )
        return order_svc.create_order(db, payload)
    except AppError as exc:
        _raise(exc)
