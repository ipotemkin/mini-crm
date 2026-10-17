"""Global search across clients and deals."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ClientStatus, DealStatus
from app.models.client import Client
from app.models.deal import Deal
from app.services.query_utils import apply_search


def global_search(
    db: Session,
    q: str,
    limit: int = 5,
    include_archived: bool = True,
) -> dict:
    if len(q.strip()) < 2:
        return {"clients": [], "deals": []}
    limit = min(max(limit, 1), 50)

    client_stmt = select(Client).where(Client.deleted_at.is_(None))
    if not include_archived:
        client_stmt = client_stmt.where(Client.is_archived.is_(False))
    client_stmt = apply_search(client_stmt, Client.search_text, q)
    clients = db.scalars(client_stmt.limit(limit)).all()

    deal_stmt = select(Deal).where(Deal.deleted_at.is_(None))
    deal_stmt = apply_search(deal_stmt, Deal.search_text, q)
    deals = db.scalars(deal_stmt.limit(limit)).all()

    return {
        "clients": [
            {
                "id": c.id,
                "name": c.name,
                "status": ClientStatus(c.status),
                "is_archived": c.is_archived,
                "updated_at": c.updated_at,
            }
            for c in clients
        ],
        "deals": [
            {
                "id": d.id,
                "title": d.title,
                "status": DealStatus(d.status),
                "client_id": d.client_id,
                "updated_at": d.updated_at,
            }
            for d in deals
        ],
    }
