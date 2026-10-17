"""Order business logic."""

from __future__ import annotations

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.enums import OrderStatus
from app.core.errors import AppError
from app.core.money import from_kopecks, to_kopecks
from app.core.normalize import normalize_text, search_tokens
from app.core.timeutils import local_today, utc_now
from app.models.client import Client
from app.models.deal import Deal
from app.models.order import Order
from app.schemas.common import Page
from app.schemas.order import (
    OrderCreate,
    OrderFilters,
    OrderListItem,
    OrderRead,
    OrderUpdate,
)
from app.services.clients import require_active_client
from app.services.numbering import next_order_number
from app.services.query_utils import apply_sort

SORT_WHITELIST = {
    "number": Order.number,
    "order_date": Order.order_date,
    "due_date": Order.due_date,
    "amount": Order.amount,
    "status": Order.status,
}


def _get_active(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None or order.deleted_at is not None:
        raise AppError("not_found", "Заказ не найден", status_code=404)
    return order


def _resolve_deal(db: Session, deal_id: int | None) -> Deal | None:
    if deal_id is None:
        return None
    deal = db.get(Deal, deal_id)
    if deal is None or deal.deleted_at is not None:
        raise AppError("not_found", "Сделка не найдена", status_code=404)
    return deal


def _to_read(db: Session, order: Order) -> OrderRead:
    client_name = None
    if order.client_id:
        client = order.client or db.get(Client, order.client_id)
        if client is None or client.deleted_at is not None:
            client_name = "Клиент удалён"
        else:
            client_name = client.name
    deal_title = None
    if order.deal_id:
        deal = order.deal or db.get(Deal, order.deal_id)
        if deal is None or deal.deleted_at is not None:
            deal_title = "Сделка удалена"
        else:
            deal_title = deal.title
    return OrderRead(
        id=order.id,
        number=order.number,
        title=order.title,
        deal_id=order.deal_id,
        deal_title=deal_title,
        client_id=order.client_id,
        client_name=client_name,
        status=OrderStatus(order.status),
        amount=from_kopecks(order.amount),
        order_date=order.order_date,
        due_date=order.due_date,
        comment=order.comment,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def get_order(db: Session, order_id: int) -> OrderRead:
    return _to_read(db, _get_active(db, order_id))


def create_order(db: Session, data: OrderCreate) -> OrderRead:
    deal = _resolve_deal(db, data.deal_id)
    client_id = data.client_id
    amount = data.amount
    if deal is not None:
        if client_id is None and deal.client_id:
            client_id = deal.client_id
        if amount is None and deal.amount is not None:
            amount = from_kopecks(deal.amount)
    require_active_client(db, client_id)
    order = Order(
        number=next_order_number(db),
        title=data.title,
        deal_id=data.deal_id,
        client_id=client_id,
        status=data.status.value,
        amount=to_kopecks(amount),
        order_date=data.order_date or local_today(),
        due_date=data.due_date,
        comment=data.comment,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return get_order(db, order.id)


def update_order(
    db: Session,
    order_id: int,
    data: OrderUpdate,
) -> OrderRead:
    order = _get_active(db, order_id)
    payload = data.model_dump(exclude_unset=True)
    if "deal_id" in payload:
        _resolve_deal(db, payload["deal_id"])
        order.deal_id = payload.pop("deal_id")
    if "client_id" in payload:
        require_active_client(db, payload["client_id"])
        order.client_id = payload.pop("client_id")
    if "amount" in payload:
        order.amount = to_kopecks(payload.pop("amount"))
    for key, value in payload.items():
        if hasattr(value, "value"):
            value = value.value
        setattr(order, key, value)
    order.updated_at = utc_now()
    db.commit()
    return get_order(db, order.id)


def delete_order(db: Session, order_id: int) -> None:
    order = _get_active(db, order_id)
    order.deleted_at = utc_now()
    db.commit()


def _apply_q(stmt: Select, q: str | None) -> Select:
    tokens = search_tokens(q or "")
    if not tokens:
        return stmt
    # Join client name via EXISTS-like OR on search fields
    for token in tokens:
        like = f"%{token}%"
        stmt = stmt.where(
            or_(
                Order.number.like(like),
                func.lower(Order.title).like(like),
                Order.client_id.in_(
                    select(Client.id).where(
                        Client.search_text.like(like),
                        Client.deleted_at.is_(None),
                    )
                ),
            )
        )
    return stmt


def _base_list_stmt(filters: OrderFilters) -> Select:
    stmt = select(Order).where(Order.deleted_at.is_(None))
    if filters.status:
        stmt = stmt.where(
            Order.status.in_([s.value for s in filters.status])
        )
    if filters.client_id:
        stmt = stmt.where(Order.client_id == filters.client_id)
    if filters.deal_id:
        stmt = stmt.where(Order.deal_id == filters.deal_id)
    if filters.date_from:
        stmt = stmt.where(Order.order_date >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(Order.order_date <= filters.date_to)
    stmt = _apply_q(stmt, filters.q)
    return stmt


def list_orders(db: Session, filters: OrderFilters) -> Page[OrderListItem]:
    stmt = _base_list_stmt(filters)
    stmt = apply_sort(stmt, filters.sort, filters.order, SORT_WHITELIST)
    total = db.scalar(
        select(func.count()).select_from(stmt.subquery())
    ) or 0
    pages = max(1, (total + filters.page_size - 1) // filters.page_size)
    page = min(filters.page, pages) if total else 1
    rows = db.scalars(
        stmt.options(
            joinedload(Order.client),
            joinedload(Order.deal),
        )
        .offset((page - 1) * filters.page_size)
        .limit(filters.page_size)
    ).unique().all()
    items = [_to_list_item(o) for o in rows]
    return Page(
        items=items,
        total=total,
        page=page,
        page_size=filters.page_size,
        pages=pages if total else 1,
    )


def list_orders_all(db: Session, filters: OrderFilters) -> list[Order]:
    stmt = _base_list_stmt(filters)
    stmt = apply_sort(stmt, filters.sort, filters.order, SORT_WHITELIST)
    return list(
        db.scalars(
            stmt.options(
                joinedload(Order.client),
                joinedload(Order.deal),
            )
        ).unique().all()
    )


def _to_list_item(order: Order) -> OrderListItem:
    client_name = None
    if order.client and order.client.deleted_at is None:
        client_name = order.client.name
    elif order.client_id:
        client_name = "Клиент удалён"
    deal_title = None
    if order.deal and order.deal.deleted_at is None:
        deal_title = order.deal.title
    elif order.deal_id:
        deal_title = "Сделка удалена"
    return OrderListItem(
        id=order.id,
        number=order.number,
        title=order.title,
        deal_id=order.deal_id,
        deal_title=deal_title,
        client_id=order.client_id,
        client_name=client_name,
        status=OrderStatus(order.status),
        amount=from_kopecks(order.amount),
        order_date=order.order_date,
        due_date=order.due_date,
    )


def sum_amounts(db: Session, filters: OrderFilters) -> int:
    stmt = _base_list_stmt(filters).with_only_columns(
        func.coalesce(func.sum(Order.amount), 0),
        maintain_column_froms=True,
    )
    return int(db.scalar(stmt) or 0)
