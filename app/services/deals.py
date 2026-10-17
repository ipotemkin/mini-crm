"""Deal business logic."""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.core.enums import (
    DEAL_CLOSED_STATUSES,
    DEAL_OPEN_STATUSES,
    DealStatus,
)
from app.core.errors import AppError
from app.core.money import from_kopecks, to_kopecks
from app.core.normalize import build_deal_search_text
from app.core.timeutils import utc_now
from app.models.client import Client
from app.models.deal import Deal
from app.models.order import Order
from app.models.task import Task
from app.schemas.common import Page
from app.schemas.deal import (
    DealCreate,
    DealFilters,
    DealListItem,
    DealRead,
    DealStatusUpdate,
    DealUpdate,
)
from app.services.clients import require_active_client
from app.services.query_utils import apply_search, apply_sort

SORT_WHITELIST = {
    "title": Deal.title,
    "status": Deal.status,
    "amount": Deal.amount,
    "expected_close_date": Deal.expected_close_date,
    "created_at": Deal.created_at,
    "updated_at": Deal.updated_at,
}


def _refresh_search(deal: Deal, client_name: str | None) -> None:
    deal.search_text = build_deal_search_text(
        deal.title,
        deal.description,
        client_name,
    )


def _get_active(db: Session, deal_id: int) -> Deal:
    deal = db.get(Deal, deal_id)
    if deal is None or deal.deleted_at is not None:
        raise AppError("not_found", "Сделка не найдена", status_code=404)
    return deal


def _client_name(db: Session, client_id: int | None) -> str | None:
    if not client_id:
        return None
    client = db.get(Client, client_id)
    if client is None:
        return None
    return client.name


def _to_read(db: Session, deal: Deal) -> DealRead:
    client = deal.client
    client_name = None
    client_archived = False
    client_deleted = False
    if deal.client_id:
        if client is None:
            client = db.get(Client, deal.client_id)
        if client is None or client.deleted_at is not None:
            client_name = "Клиент удалён"
            client_deleted = True
        else:
            client_name = client.name
            client_archived = client.is_archived
    return DealRead(
        id=deal.id,
        title=deal.title,
        client_id=deal.client_id,
        client_name=client_name,
        client_archived=client_archived,
        client_deleted=client_deleted,
        status=DealStatus(deal.status),
        amount=from_kopecks(deal.amount),
        expected_close_date=deal.expected_close_date,
        closed_at=deal.closed_at,
        lost_reason=deal.lost_reason,
        description=deal.description,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
    )


def get_deal(db: Session, deal_id: int) -> DealRead:
    deal = _get_active(db, deal_id)
    return _to_read(db, deal)


def _apply_status(deal: Deal, status: DealStatus, lost_reason: str | None) -> None:
    deal.status = status.value
    if status in DEAL_CLOSED_STATUSES:
        if deal.closed_at is None:
            deal.closed_at = utc_now()
        if status == DealStatus.LOST and lost_reason is not None:
            deal.lost_reason = lost_reason
    else:
        deal.closed_at = None


def create_deal(db: Session, data: DealCreate) -> DealRead:
    client = require_active_client(db, data.client_id)
    deal = Deal(
        title=data.title,
        client_id=data.client_id,
        status=data.status.value,
        amount=to_kopecks(data.amount),
        expected_close_date=data.expected_close_date,
        lost_reason=data.lost_reason,
        description=data.description,
    )
    _apply_status(deal, data.status, data.lost_reason)
    _refresh_search(deal, client.name if client else None)
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return get_deal(db, deal.id)


def update_deal(
    db: Session,
    deal_id: int,
    data: DealUpdate,
) -> DealRead:
    deal = _get_active(db, deal_id)
    payload = data.model_dump(exclude_unset=True)
    if "client_id" in payload:
        require_active_client(db, payload["client_id"])
        deal.client_id = payload.pop("client_id")
    if "amount" in payload:
        deal.amount = to_kopecks(payload.pop("amount"))
    if "status" in payload:
        status = payload.pop("status")
        lost = payload.pop("lost_reason", deal.lost_reason)
        _apply_status(deal, status, lost)
    for key, value in payload.items():
        if hasattr(value, "value"):
            value = value.value
        setattr(deal, key, value)
    _refresh_search(deal, _client_name(db, deal.client_id))
    deal.updated_at = utc_now()
    db.commit()
    return get_deal(db, deal.id)


def set_deal_status(
    db: Session,
    deal_id: int,
    data: DealStatusUpdate,
) -> DealRead:
    deal = _get_active(db, deal_id)
    _apply_status(deal, data.status, data.lost_reason)
    deal.updated_at = utc_now()
    db.commit()
    return get_deal(db, deal.id)


def attach_client(
    db: Session,
    deal_id: int,
    client_id: int,
) -> DealRead:
    deal = _get_active(db, deal_id)
    client = require_active_client(db, client_id)
    assert client is not None
    deal.client_id = client.id
    _refresh_search(deal, client.name)
    deal.updated_at = utc_now()
    db.commit()
    return get_deal(db, deal.id)


def detach_client(db: Session, deal_id: int) -> DealRead:
    deal = _get_active(db, deal_id)
    deal.client_id = None
    _refresh_search(deal, None)
    deal.updated_at = utc_now()
    db.commit()
    return get_deal(db, deal.id)


def delete_deal(db: Session, deal_id: int) -> dict[str, int]:
    deal = _get_active(db, deal_id)
    now = utc_now()
    deal.deleted_at = now
    tasks = db.scalars(
        select(Task).where(
            Task.deal_id == deal.id,
            Task.deleted_at.is_(None),
        )
    ).all()
    for task in tasks:
        task.deleted_at = now
    orders_count = db.scalar(
        select(func.count()).where(
            Order.deal_id == deal.id,
            Order.deleted_at.is_(None),
        )
    ) or 0
    db.commit()
    return {"tasks": len(tasks), "orders": orders_count}


def delete_impact(db: Session, deal_id: int) -> dict[str, int]:
    deal = _get_active(db, deal_id)
    tasks = db.scalar(
        select(func.count()).where(
            Task.deal_id == deal.id,
            Task.deleted_at.is_(None),
        )
    ) or 0
    orders = db.scalar(
        select(func.count()).where(
            Order.deal_id == deal.id,
            Order.deleted_at.is_(None),
        )
    ) or 0
    return {"tasks": tasks, "orders": orders}


def _base_list_stmt(filters: DealFilters) -> Select:
    stmt = select(Deal).where(Deal.deleted_at.is_(None))
    if filters.group == "open":
        stmt = stmt.where(
            Deal.status.in_([s.value for s in DEAL_OPEN_STATUSES])
        )
    elif filters.group == "closed":
        stmt = stmt.where(
            Deal.status.in_([s.value for s in DEAL_CLOSED_STATUSES])
        )
    if filters.status:
        stmt = stmt.where(
            Deal.status.in_([s.value for s in filters.status])
        )
    if filters.no_client:
        stmt = stmt.where(Deal.client_id.is_(None))
    elif filters.client_id:
        stmt = stmt.where(Deal.client_id == filters.client_id)
    if filters.amount_min is not None:
        stmt = stmt.where(Deal.amount >= to_kopecks(filters.amount_min))
    if filters.amount_max is not None:
        stmt = stmt.where(Deal.amount <= to_kopecks(filters.amount_max))
    if filters.close_from:
        stmt = stmt.where(Deal.expected_close_date >= filters.close_from)
    if filters.close_to:
        stmt = stmt.where(Deal.expected_close_date <= filters.close_to)
    stmt = apply_search(stmt, Deal.search_text, filters.q)
    return stmt


def list_deals(db: Session, filters: DealFilters) -> Page[DealListItem]:
    stmt = _base_list_stmt(filters)
    stmt = apply_sort(stmt, filters.sort, filters.order, SORT_WHITELIST)
    total = db.scalar(
        select(func.count()).select_from(stmt.subquery())
    ) or 0
    pages = max(1, (total + filters.page_size - 1) // filters.page_size)
    page = min(filters.page, pages) if total else 1
    rows = db.scalars(
        stmt.options(joinedload(Deal.client))
        .offset((page - 1) * filters.page_size)
        .limit(filters.page_size)
    ).unique().all()
    items = [
        DealListItem(
            id=d.id,
            title=d.title,
            client_id=d.client_id,
            client_name=(
                d.client.name
                if d.client and d.client.deleted_at is None
                else ("Клиент удалён" if d.client_id else None)
            ),
            status=DealStatus(d.status),
            amount=from_kopecks(d.amount),
            expected_close_date=d.expected_close_date,
            updated_at=d.updated_at,
        )
        for d in rows
    ]
    return Page(
        items=items,
        total=total,
        page=page,
        page_size=filters.page_size,
        pages=pages if total else 1,
    )


def list_deals_all(db: Session, filters: DealFilters) -> list[Deal]:
    stmt = _base_list_stmt(filters)
    stmt = apply_sort(stmt, filters.sort, filters.order, SORT_WHITELIST)
    return list(
        db.scalars(stmt.options(joinedload(Deal.client))).unique().all()
    )


def sum_amounts(db: Session, filters: DealFilters) -> int:
    stmt = _base_list_stmt(filters).with_only_columns(
        func.coalesce(func.sum(Deal.amount), 0),
        maintain_column_froms=True,
    )
    return int(db.scalar(stmt) or 0)


def lookup_deals(
    db: Session,
    q: str,
    limit: int = 10,
) -> list[dict]:
    if len(q.strip()) < 2:
        return []
    stmt = select(Deal).where(Deal.deleted_at.is_(None))
    stmt = apply_search(stmt, Deal.search_text, q)
    deals = db.scalars(stmt.limit(min(limit, 10))).all()
    return [{"id": d.id, "title": d.title} for d in deals]
