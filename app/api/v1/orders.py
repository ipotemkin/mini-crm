"""Orders API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from app.api.deps import AuthUser, Csrf, DbSession
from app.core.errors import AppError
from app.core.enums import OrderStatus
from app.core.money import from_kopecks
from app.schemas.order import OrderCreate, OrderFilters, OrderUpdate
from app.services import orders as svc

router = APIRouter(prefix="/orders", tags=["orders"])


def _raise(exc: AppError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail=exc.as_http_detail(),
    )


@router.get("")
def list_orders(
    db: DbSession,
    _user: AuthUser,
    q: str | None = None,
    status: list[OrderStatus] | None = Query(default=None),
    client_id: int | None = None,
    deal_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort: str = "order_date",
    order: str = "desc",
    page: int = 1,
    page_size: int = 25,
):
    try:
        filters = OrderFilters(
            q=q,
            status=status,
            client_id=client_id,
            deal_id=deal_id,
            date_from=date_from,
            date_to=date_to,
            sort=sort,
            order=order,  # type: ignore[arg-type]
            page=page,
            page_size=page_size,
        )
        page_data = svc.list_orders(db, filters)
        total_amount = from_kopecks(svc.sum_amounts(db, filters))
        return {**page_data.model_dump(), "total_amount": total_amount}
    except AppError as exc:
        _raise(exc)


@router.post("", status_code=201)
def create_order(
    body: OrderCreate,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
):
    try:
        return svc.create_order(db, body)
    except AppError as exc:
        _raise(exc)


@router.get("/{order_id}")
def get_order(order_id: int, db: DbSession, _user: AuthUser):
    try:
        return svc.get_order(db, order_id)
    except AppError as exc:
        _raise(exc)


@router.patch("/{order_id}")
def patch_order(
    order_id: int,
    body: OrderUpdate,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
):
    try:
        return svc.update_order(db, order_id, body)
    except AppError as exc:
        _raise(exc)


@router.delete("/{order_id}", status_code=204)
def delete_order(
    order_id: int,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
):
    try:
        svc.delete_order(db, order_id)
    except AppError as exc:
        _raise(exc)
    return Response(status_code=204)
