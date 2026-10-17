"""Clients HTML pages."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.enums import ClientStatus, ClientType
from app.core.errors import AppError
from app.db import get_db
from app.schemas.client import ClientCreate, ClientFilters, ClientUpdate
from app.schemas.deal import DealFilters
from app.schemas.order import OrderFilters
from app.schemas.task import TaskFilters
from app.services import clients as svc
from app.services import deals as deal_svc
from app.services import orders as order_svc
from app.services import tasks as task_svc
from app.web.deps import render, require_web_user

router = APIRouter(prefix="/clients", tags=["web-clients"])


@router.get("")
def list_page(
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
    q: str | None = None,
    archived: str = "active",
    status: list[str] | None = Query(default=None),
    client_type: str | None = None,
    sort: str = "updated_at",
    order: str = "desc",
    page: int = 1,
    page_size: int = 25,
):
    statuses = [ClientStatus(s) for s in (status or [])]
    filters = ClientFilters(
        q=q,
        archived=archived,  # type: ignore[arg-type]
        status=statuses or None,
        client_type=ClientType(client_type) if client_type else None,
        sort=sort,
        order=order,  # type: ignore[arg-type]
        page=page,
        page_size=page_size,
    )
    result = svc.list_clients(db, filters)
    return render(
        request,
        "clients/list.html",
        {
            "page_data": result,
            "filters": filters,
            "statuses": list(ClientStatus),
            "types": list(ClientType),
        },
    )


@router.get("/new")
def new_form(
    request: Request,
    _user=Depends(require_web_user),
):
    return render(
        request,
        "clients/form.html",
        {
            "client": None,
            "statuses": list(ClientStatus),
            "types": list(ClientType),
        },
    )


@router.post("/new")
def create(
    request: Request,
    name: str = Form(...),
    client_type: str = Form("company"),
    contact_person: str | None = Form(None),
    phone: str | None = Form(None),
    email: str | None = Form(None),
    status: str = Form("lead"),
    source: str | None = Form(None),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    try:
        created = svc.create_client(
            db,
            ClientCreate(
                name=name,
                client_type=ClientType(client_type),
                contact_person=contact_person or None,
                phone=phone or None,
                email=email or None,
                status=ClientStatus(status),
                source=source or None,
                notes=notes or None,
            ),
        )
        return RedirectResponse(
            f"/clients/{created.id}?flash=Клиент+создан",
            status_code=303,
        )
    except Exception as exc:
        return render(
            request,
            "clients/form.html",
            {
                "client": None,
                "error": str(exc),
                "form": {
                    "name": name,
                    "client_type": client_type,
                    "contact_person": contact_person,
                    "phone": phone,
                    "email": email,
                    "status": status,
                    "source": source,
                    "notes": notes,
                },
                "statuses": list(ClientStatus),
                "types": list(ClientType),
            },
            status_code=422,
        )


@router.get("/{client_id}")
def detail(
    client_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    try:
        client = svc.get_client(db, client_id)
    except AppError:
        return render(request, "errors/404.html", status_code=404)
    deals = deal_svc.list_deals(
        db,
        DealFilters(client_id=client_id, group="all", page_size=50),
    )
    orders = order_svc.list_orders(
        db,
        OrderFilters(client_id=client_id, page_size=50),
    )
    tasks = task_svc.list_tasks(
        db,
        TaskFilters(view="all", page_size=100),
        include_deal_client=client_id,
    )
    impact = svc.delete_impact(db, client_id)
    return render(
        request,
        "clients/detail.html",
        {
            "client": client,
            "deals": deals.items,
            "orders": orders.items,
            "tasks": tasks.items,
            "impact": impact,
            "statuses": list(ClientStatus),
        },
    )


@router.get("/{client_id}/edit")
def edit_form(
    client_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    try:
        client = svc.get_client(db, client_id)
    except AppError:
        return render(request, "errors/404.html", status_code=404)
    return render(
        request,
        "clients/form.html",
        {
            "client": client,
            "statuses": list(ClientStatus),
            "types": list(ClientType),
        },
    )


@router.post("/{client_id}/edit")
def edit_submit(
    client_id: int,
    name: str = Form(...),
    client_type: str = Form("company"),
    contact_person: str | None = Form(None),
    phone: str | None = Form(None),
    email: str | None = Form(None),
    status: str = Form("lead"),
    source: str | None = Form(None),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    svc.update_client(
        db,
        client_id,
        ClientUpdate(
            name=name,
            client_type=ClientType(client_type),
            contact_person=contact_person or None,
            phone=phone or None,
            email=email or None,
            status=ClientStatus(status),
            source=source or None,
            notes=notes or None,
        ),
    )
    return RedirectResponse(
        f"/clients/{client_id}?flash=Сохранено",
        status_code=303,
    )


@router.post("/{client_id}/status")
def change_status(
    client_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    svc.update_client(
        db,
        client_id,
        ClientUpdate(status=ClientStatus(status)),
    )
    return RedirectResponse(
        f"/clients/{client_id}?flash=Статус+обновлён",
        status_code=303,
    )


@router.post("/{client_id}/archive")
def archive(
    client_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    svc.archive_client(db, client_id)
    return RedirectResponse(
        f"/clients/{client_id}?flash=В+архиве",
        status_code=303,
    )


@router.post("/{client_id}/unarchive")
def unarchive(
    client_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    svc.unarchive_client(db, client_id)
    return RedirectResponse(
        f"/clients/{client_id}?flash=Возвращён+из+архива",
        status_code=303,
    )


@router.post("/{client_id}/delete")
def delete(
    client_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_web_user),
):
    svc.delete_client(db, client_id)
    return RedirectResponse(
        "/clients?flash=Клиент+удалён",
        status_code=303,
    )
