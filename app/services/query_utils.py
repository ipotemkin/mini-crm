"""Shared query helpers: search, sort, pagination."""

from __future__ import annotations

from typing import Any

from sqlalchemy import ColumnElement, Select, asc, desc, func, or_
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.normalize import search_tokens
from app.schemas.common import Page


def apply_search(
    stmt: Select[Any],
    column: ColumnElement[str],
    query: str | None,
) -> Select[Any]:
    tokens = search_tokens(query or "")
    for token in tokens:
        stmt = stmt.where(column.like(f"%{token}%"))
    return stmt


def apply_sort(
    stmt: Select[Any],
    sort: str,
    order: str,
    whitelist: dict[str, Any],
    default: str = "updated_at",
) -> Select[Any]:
    column = whitelist.get(sort) or whitelist.get(default)
    if column is None:
        raise AppError(
            "bad_request",
            "Недопустимое поле сортировки",
            status_code=400,
        )
    direction = desc if order == "desc" else asc
    # Nulls last for due_at-like columns via SQLite default
    return stmt.order_by(direction(column))


def paginate(
    db: Session,
    stmt: Select[Any],
    page: int,
    page_size: int,
) -> tuple[list[Any], Page[Any]]:
    count_stmt = select_count(stmt)
    total = db.scalar(count_stmt) or 0
    pages = max(1, (total + page_size - 1) // page_size) if total else 1
    page = min(page, pages)
    items = list(
        db.scalars(
            stmt.offset((page - 1) * page_size).limit(page_size)
        ).all()
    )
    meta = Page(
        items=[],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )
    return items, meta


def select_count(stmt: Select[Any]) -> Select[Any]:
    return stmt.order_by(None).with_only_columns(
        func.count(),
        maintain_column_froms=True,
    )


def not_deleted(column: ColumnElement[Any]) -> ColumnElement[bool]:
    return column.is_(None)


def or_none(*conditions: ColumnElement[Any]) -> ColumnElement[bool]:
    return or_(*conditions)
