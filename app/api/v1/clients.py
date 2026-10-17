"""Clients API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from app.api.deps import AuthUser, Csrf, DbSession
from app.core.errors import AppError
from app.core.enums import ClientStatus, ClientType
from app.schemas.client import (
    ClientCreate,
    ClientFilters,
    ClientUpdate,
)
from app.schemas.deal import DealFilters
from app.schemas.order import OrderFilters
from app.schemas.task import TaskFilters
from app.services import clients as svc
from app.services import deals as deal_svc
from app.services import orders as order_svc
from app.services import tasks as task_svc

router = APIRouter(prefix="/clients", tags=["clients"])


def _raise(exc: AppError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail=exc.as_http_detail(),
    )


@router.get("")
def list_clients(
    db: DbSession,
    _user: AuthUser,
    q: str | None = None,
    status: list[ClientStatus] | None = Query(default=None),
    archived: str = "active",
    client_type: ClientType | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    sort: str = "updated_at",
    order: str = "desc",
    page: int = 1,
    page_size: int = 25,
):
    try:
        filters = ClientFilters(
            q=q,
            status=status,
            archived=archived,  # type: ignore[arg-type]
            client_type=client_type,
            created_from=created_from,
            created_to=created_to,
            sort=sort,
            order=order,  # type: ignore[arg-type]
            page=page,
            page_size=page_size,
        )
        return svc.list_clients(db, filters)
    except AppError as exc:
        _raise(exc)


@router.post("", status_code=201)
def create_client(
    body: ClientCreate,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
):
    try:
        return svc.create_client(db, body)
    except AppError as exc:
        _raise(exc)


@router.get("/duplicates")
def duplicates(
    db: DbSession,
    _user: AuthUser,
    email: str | None = None,
    phone: str | None = None,
    exclude_id: int | None = None,
):
    return svc.find_duplicates(db, email, phone, exclude_id)


@router.get("/lookup")
def lookup(
    db: DbSession,
    _user: AuthUser,
    q: str = "",
    limit: int = 10,
):
    return svc.lookup_clients(db, q, limit)


@router.get("/{client_id}")
def get_client(client_id: int, db: DbSession, _user: AuthUser):
    try:
        return svc.get_client(db, client_id)
    except AppError as exc:
        _raise(exc)


@router.patch("/{client_id}")
def patch_client(
    client_id: int,
    body: ClientUpdate,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
):
    try:
        return svc.update_client(db, client_id, body)
    except AppError as exc:
        _raise(exc)


@router.post("/{client_id}/archive")
def archive(client_id: int, db: DbSession, _user: AuthUser, _csrf: Csrf):
    try:
        return svc.archive_client(db, client_id)
    except AppError as exc:
        _raise(exc)


@router.post("/{client_id}/unarchive")
def unarchive(client_id: int, db: DbSession, _user: AuthUser, _csrf: Csrf):
    try:
        return svc.unarchive_client(db, client_id)
    except AppError as exc:
        _raise(exc)


@router.delete("/{client_id}", status_code=204)
def delete_client(
    client_id: int,
    db: DbSession,
    _user: AuthUser,
    _csrf: Csrf,
):
    try:
        svc.delete_client(db, client_id)
    except AppError as exc:
        _raise(exc)
    return Response(status_code=204)


@router.get("/{client_id}/delete-impact")
def impact(client_id: int, db: DbSession, _user: AuthUser):
    try:
        return svc.delete_impact(db, client_id)
    except AppError as exc:
        _raise(exc)


@router.get("/{client_id}/deals")
def client_deals(
    client_id: int,
    db: DbSession,
    _user: AuthUser,
    status: list[str] | None = Query(default=None),
    page: int = 1,
    page_size: int = 25,
):
    svc.get_client(db, client_id)
    filters = DealFilters(
        client_id=client_id,
        group="all",
        page=page,
        page_size=page_size,
    )
    return deal_svc.list_deals(db, filters)


@router.get("/{client_id}/orders")
def client_orders(
    client_id: int,
    db: DbSession,
    _user: AuthUser,
    page: int = 1,
    page_size: int = 25,
):
    svc.get_client(db, client_id)
    return order_svc.list_orders(
        db,
        OrderFilters(
            client_id=client_id,
            page=page,
            page_size=page_size,
        ),
    )


@router.get("/{client_id}/tasks")
def client_tasks(
    client_id: int,
    db: DbSession,
    _user: AuthUser,
    is_done: bool | None = None,
    page: int = 1,
    page_size: int = 50,
):
    svc.get_client(db, client_id)
    view = "all"
    if is_done is True:
        view = "done"
    elif is_done is False:
        view = "active"
    return task_svc.list_tasks(
        db,
        TaskFilters(view=view, page=page, page_size=page_size),
        include_deal_client=client_id,
    )
