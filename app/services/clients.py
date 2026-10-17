"""Client business logic."""

from __future__ import annotations

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.enums import DEAL_OPEN_STATUSES, ClientStatus
from app.core.errors import AppError
from app.core.normalize import (
    build_client_search_text,
    digits_only,
    search_tokens,
)
from app.core.timeutils import utc_now
from app.models.client import Client
from app.models.deal import Deal
from app.models.order import Order
from app.models.task import Task
from app.schemas.client import (
    ClientCreate,
    ClientFilters,
    ClientListItem,
    ClientLookupItem,
    ClientRead,
    ClientUpdate,
    DeleteImpact,
)
from app.schemas.common import Page
from app.services.query_utils import apply_search, apply_sort


SORT_WHITELIST = {
    "name": Client.name,
    "status": Client.status,
    "created_at": Client.created_at,
    "updated_at": Client.updated_at,
}


def _refresh_search(client: Client) -> None:
    client.search_text = build_client_search_text(
        client.name,
        client.contact_person,
        client.email,
        client.phone,
        client.source,
        client.notes,
    )


def _get_active(db: Session, client_id: int) -> Client:
    client = db.get(Client, client_id)
    if client is None or client.deleted_at is not None:
        raise AppError("not_found", "Клиент не найден", status_code=404)
    return client


def get_client(db: Session, client_id: int) -> ClientRead:
    client = _get_active(db, client_id)
    open_deals = db.scalar(
        select(func.count())
        .select_from(Deal)
        .where(
            Deal.client_id == client.id,
            Deal.deleted_at.is_(None),
            Deal.status.in_([s.value for s in DEAL_OPEN_STATUSES]),
        )
    ) or 0
    open_tasks = db.scalar(
        select(func.count())
        .select_from(Task)
        .where(
            Task.client_id == client.id,
            Task.deleted_at.is_(None),
            Task.is_done.is_(False),
        )
    ) or 0
    return ClientRead(
        id=client.id,
        name=client.name,
        client_type=client.client_type,
        contact_person=client.contact_person,
        phone=client.phone,
        email=client.email,
        status=client.status,
        source=client.source,
        notes=client.notes,
        is_archived=client.is_archived,
        archived_at=client.archived_at,
        created_at=client.created_at,
        updated_at=client.updated_at,
        open_deals_count=open_deals,
        open_tasks_count=open_tasks,
    )


def create_client(db: Session, data: ClientCreate) -> ClientRead:
    client = Client(
        name=data.name,
        client_type=data.client_type.value,
        contact_person=data.contact_person,
        phone=data.phone,
        email=str(data.email) if data.email else None,
        status=data.status.value,
        source=data.source,
        notes=data.notes,
    )
    _refresh_search(client)
    db.add(client)
    db.commit()
    db.refresh(client)
    return get_client(db, client.id)


def update_client(
    db: Session,
    client_id: int,
    data: ClientUpdate,
) -> ClientRead:
    client = _get_active(db, client_id)
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        if key == "email" and value is not None:
            value = str(value)
        if hasattr(value, "value"):
            value = value.value
        setattr(client, key, value)
    _refresh_search(client)
    client.updated_at = utc_now()
    db.commit()
    # Refresh deal search texts if name changed
    if "name" in payload:
        _refresh_client_deals_search(db, client)
    return get_client(db, client.id)


def _refresh_client_deals_search(db: Session, client: Client) -> None:
    from app.core.normalize import build_deal_search_text

    deals = db.scalars(
        select(Deal).where(
            Deal.client_id == client.id,
            Deal.deleted_at.is_(None),
        )
    ).all()
    for deal in deals:
        deal.search_text = build_deal_search_text(
            deal.title,
            deal.description,
            client.name,
        )
    db.commit()


def archive_client(db: Session, client_id: int) -> ClientRead:
    client = _get_active(db, client_id)
    client.is_archived = True
    client.archived_at = utc_now()
    client.updated_at = utc_now()
    db.commit()
    return get_client(db, client.id)


def unarchive_client(db: Session, client_id: int) -> ClientRead:
    client = _get_active(db, client_id)
    client.is_archived = False
    client.archived_at = None
    client.updated_at = utc_now()
    db.commit()
    return get_client(db, client.id)


def delete_client(db: Session, client_id: int) -> None:
    client = _get_active(db, client_id)
    now = utc_now()
    client.deleted_at = now
    client.updated_at = now
    tasks = db.scalars(
        select(Task).where(
            Task.client_id == client.id,
            Task.deleted_at.is_(None),
        )
    ).all()
    for task in tasks:
        task.deleted_at = now
    db.commit()


def delete_impact(db: Session, client_id: int) -> DeleteImpact:
    client = _get_active(db, client_id)
    deals = db.scalar(
        select(func.count()).where(
            Deal.client_id == client.id,
            Deal.deleted_at.is_(None),
        )
    ) or 0
    open_deals = db.scalar(
        select(func.count()).where(
            Deal.client_id == client.id,
            Deal.deleted_at.is_(None),
            Deal.status.in_([s.value for s in DEAL_OPEN_STATUSES]),
        )
    ) or 0
    orders = db.scalar(
        select(func.count()).where(
            Order.client_id == client.id,
            Order.deleted_at.is_(None),
        )
    ) or 0
    tasks = db.scalar(
        select(func.count()).where(
            Task.client_id == client.id,
            Task.deleted_at.is_(None),
        )
    ) or 0
    open_tasks = db.scalar(
        select(func.count()).where(
            Task.client_id == client.id,
            Task.deleted_at.is_(None),
            Task.is_done.is_(False),
        )
    ) or 0
    return DeleteImpact(
        deals=deals,
        orders=orders,
        tasks=tasks,
        open_deals=open_deals,
        open_tasks=open_tasks,
    )


def find_duplicates(
    db: Session,
    email: str | None,
    phone: str | None,
    exclude_id: int | None = None,
) -> list[ClientLookupItem]:
    conditions = []
    if email:
        conditions.append(func.lower(Client.email) == email.lower())
    phone_digits = digits_only(phone)
    if phone_digits:
        conditions.append(
            Client.search_text.like(f"%{phone_digits}%")
        )
    if not conditions:
        return []
    stmt = select(Client).where(
        Client.deleted_at.is_(None),
        or_(*conditions),
    )
    if exclude_id:
        stmt = stmt.where(Client.id != exclude_id)
    clients = db.scalars(stmt.limit(10)).all()
    return [
        ClientLookupItem(
            id=c.id,
            name=c.name,
            phone=c.phone,
            email=c.email,
        )
        for c in clients
    ]


def lookup_clients(
    db: Session,
    q: str,
    limit: int = 10,
) -> list[ClientLookupItem]:
    if len(q.strip()) < 2:
        return []
    stmt = (
        select(Client)
        .where(
            Client.deleted_at.is_(None),
            Client.is_archived.is_(False),
        )
    )
    stmt = apply_search(stmt, Client.search_text, q)
    clients = db.scalars(stmt.limit(min(limit, 10))).all()
    return [
        ClientLookupItem(
            id=c.id,
            name=c.name,
            phone=c.phone,
            email=c.email,
        )
        for c in clients
    ]


def _base_list_stmt(filters: ClientFilters) -> Select:
    stmt = select(Client).where(Client.deleted_at.is_(None))
    if filters.archived == "active":
        stmt = stmt.where(Client.is_archived.is_(False))
    elif filters.archived == "archived":
        stmt = stmt.where(Client.is_archived.is_(True))
    if filters.status:
        stmt = stmt.where(
            Client.status.in_([s.value for s in filters.status])
        )
    if filters.client_type:
        stmt = stmt.where(Client.client_type == filters.client_type.value)
    if filters.created_from:
        stmt = stmt.where(
            func.date(Client.created_at) >= filters.created_from
        )
    if filters.created_to:
        stmt = stmt.where(
            func.date(Client.created_at) <= filters.created_to
        )
    stmt = apply_search(stmt, Client.search_text, filters.q)
    return stmt


def list_clients(
    db: Session,
    filters: ClientFilters,
) -> Page[ClientListItem]:
    stmt = _base_list_stmt(filters)
    stmt = apply_sort(
        stmt,
        filters.sort,
        filters.order,
        SORT_WHITELIST,
    )
    total = db.scalar(
        select(func.count()).select_from(stmt.subquery())
    ) or 0
    pages = max(1, (total + filters.page_size - 1) // filters.page_size)
    page = min(filters.page, pages) if total else 1
    rows = db.scalars(
        stmt.offset((page - 1) * filters.page_size).limit(
            filters.page_size
        )
    ).all()
    items = [_to_list_item(db, c) for c in rows]
    return Page(
        items=items,
        total=total,
        page=page,
        page_size=filters.page_size,
        pages=pages if total else 1,
    )


def list_clients_all(
    db: Session,
    filters: ClientFilters,
) -> list[Client]:
    """All matching rows for export (no pagination)."""
    stmt = _base_list_stmt(filters)
    stmt = apply_sort(
        stmt,
        filters.sort,
        filters.order,
        SORT_WHITELIST,
    )
    return list(db.scalars(stmt).all())


def _to_list_item(db: Session, client: Client) -> ClientListItem:
    open_deals = db.scalar(
        select(func.count()).where(
            Deal.client_id == client.id,
            Deal.deleted_at.is_(None),
            Deal.status.in_([s.value for s in DEAL_OPEN_STATUSES]),
        )
    ) or 0
    next_due = db.scalar(
        select(Task.due_at)
        .where(
            Task.client_id == client.id,
            Task.deleted_at.is_(None),
            Task.is_done.is_(False),
            Task.due_at.is_not(None),
        )
        .order_by(Task.due_at.asc())
        .limit(1)
    )
    return ClientListItem(
        id=client.id,
        name=client.name,
        client_type=client.client_type,
        contact_person=client.contact_person,
        phone=client.phone,
        email=client.email,
        status=client.status,
        is_archived=client.is_archived,
        updated_at=client.updated_at,
        open_deals_count=open_deals,
        next_task_due_at=next_due,
    )


def require_active_client(
    db: Session,
    client_id: int | None,
    *,
    allow_archived: bool = False,
) -> Client | None:
    if client_id is None:
        return None
    client = _get_active(db, client_id)
    if client.is_archived and not allow_archived:
        raise AppError(
            "conflict",
            "Нельзя привязать архивного клиента",
            status_code=409,
        )
    return client
