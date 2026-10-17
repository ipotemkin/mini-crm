"""Task and reminder business logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.enums import TaskType
from app.core.errors import AppError
from app.core.normalize import normalize_text, search_tokens
from app.core.timeutils import (
    all_day_due_at,
    app_tz,
    local_day_bounds,
    local_today,
    to_utc,
    utc_now,
)
from app.models.client import Client
from app.models.deal import Deal
from app.models.task import Task
from app.schemas.common import Page
from app.schemas.task import (
    ReminderSummary,
    TaskCreate,
    TaskFilters,
    TaskListItem,
    TaskRead,
    TaskUpdate,
)
from app.services.clients import require_active_client
from app.services.query_utils import apply_sort

SORT_WHITELIST = {
    "due_at": Task.due_at,
    "created_at": Task.created_at,
    "title": Task.title,
}


def due_state_for(task: Task, now: datetime | None = None) -> str:
    if task.is_done:
        return "done"
    if task.due_at is None:
        return "no_due"
    now = now or utc_now()
    due = task.due_at
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    start, end = local_day_bounds(local_today())
    if due < now and due < start:
        return "overdue"
    if due < now and start <= due <= end:
        return "overdue"
    if start <= due <= end:
        return "today"
    if due > end:
        return "upcoming"
    return "no_due"


def _get_active(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.deleted_at is not None:
        raise AppError("not_found", "Задача не найдена", status_code=404)
    return task


def _resolve_deal(db: Session, deal_id: int | None) -> Deal | None:
    if deal_id is None:
        return None
    deal = db.get(Deal, deal_id)
    if deal is None or deal.deleted_at is not None:
        raise AppError("not_found", "Сделка не найдена", status_code=404)
    return deal


def _resolve_due(data: TaskCreate | TaskUpdate) -> tuple[datetime | None, bool]:
    all_day = getattr(data, "all_day", False) or False
    if getattr(data, "clear_due", False):
        return None, False
    if data.due_at is not None:
        return to_utc(data.due_at), all_day
    if getattr(data, "due_date", None) is not None:
        return all_day_due_at(data.due_date), True
    return None, all_day


def _to_read(db: Session, task: Task) -> TaskRead:
    client_name = None
    if task.client_id:
        client = task.client or db.get(Client, task.client_id)
        if client and client.deleted_at is None:
            client_name = client.name
        else:
            client_name = "Клиент удалён"
    deal_title = None
    if task.deal_id:
        deal = task.deal or db.get(Deal, task.deal_id)
        if deal and deal.deleted_at is None:
            deal_title = deal.title
        else:
            deal_title = "Сделка удалена"
    return TaskRead(
        id=task.id,
        title=task.title,
        task_type=TaskType(task.task_type),
        description=task.description,
        due_at=task.due_at,
        all_day=task.all_day,
        is_done=task.is_done,
        done_at=task.done_at,
        client_id=task.client_id,
        client_name=client_name,
        deal_id=task.deal_id,
        deal_title=deal_title,
        due_state=due_state_for(task),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def get_task(db: Session, task_id: int) -> TaskRead:
    return _to_read(db, _get_active(db, task_id))


def create_task(db: Session, data: TaskCreate) -> TaskRead:
    require_active_client(db, data.client_id)
    _resolve_deal(db, data.deal_id)
    due_at, all_day = _resolve_due(data)
    task = Task(
        title=data.title,
        task_type=data.task_type.value,
        description=data.description,
        due_at=due_at,
        all_day=all_day or data.all_day,
        client_id=data.client_id,
        deal_id=data.deal_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return get_task(db, task.id)


def update_task(
    db: Session,
    task_id: int,
    data: TaskUpdate,
) -> TaskRead:
    task = _get_active(db, task_id)
    payload = data.model_dump(exclude_unset=True)
    if "client_id" in payload:
        require_active_client(db, payload["client_id"])
        task.client_id = payload.pop("client_id")
    if "deal_id" in payload:
        _resolve_deal(db, payload["deal_id"])
        task.deal_id = payload.pop("deal_id")
    due_fields = {"due_at", "due_date", "all_day", "clear_due"}
    if due_fields & set(payload.keys()):
        due_at, all_day = _resolve_due(data)
        if "clear_due" in payload and payload["clear_due"]:
            task.due_at = None
            task.all_day = False
        else:
            if data.due_at is not None or data.due_date is not None:
                task.due_at = due_at
            if data.all_day is not None:
                task.all_day = data.all_day
            elif data.due_date is not None:
                task.all_day = True
        for key in due_fields:
            payload.pop(key, None)
    for key, value in payload.items():
        if hasattr(value, "value"):
            value = value.value
        setattr(task, key, value)
    task.updated_at = utc_now()
    db.commit()
    return get_task(db, task.id)


def complete_task(db: Session, task_id: int) -> TaskRead:
    task = _get_active(db, task_id)
    task.is_done = True
    task.done_at = utc_now()
    task.updated_at = utc_now()
    db.commit()
    return get_task(db, task.id)


def reopen_task(db: Session, task_id: int) -> TaskRead:
    task = _get_active(db, task_id)
    task.is_done = False
    task.done_at = None
    task.updated_at = utc_now()
    db.commit()
    return get_task(db, task.id)


def snooze_task(
    db: Session,
    task_id: int,
    mode: str,
) -> TaskRead:
    task = _get_active(db, task_id)
    now = utc_now()
    base = task.due_at or now
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    if mode == "1h":
        task.due_at = base + timedelta(hours=1)
        task.all_day = False
    elif mode == "tomorrow":
        day = (datetime.now(app_tz()) + timedelta(days=1)).date()
        task.due_at = all_day_due_at(day)
        task.all_day = True
    elif mode == "1w":
        task.due_at = base + timedelta(weeks=1)
    else:
        raise AppError("bad_request", "Неизвестный режим переноса")
    task.updated_at = now
    db.commit()
    return get_task(db, task.id)


def delete_task(db: Session, task_id: int) -> None:
    task = _get_active(db, task_id)
    task.deleted_at = utc_now()
    db.commit()


def _apply_q(stmt: Select, q: str | None) -> Select:
    for token in search_tokens(q or ""):
        like = f"%{token}%"
        stmt = stmt.where(
            or_(
                func.lower(Task.title).like(like),
                func.lower(func.coalesce(Task.description, "")).like(like),
            )
        )
    return stmt


def _base_list_stmt(
    filters: TaskFilters,
    *,
    include_deal_client: int | None = None,
) -> Select:
    stmt = select(Task).where(Task.deleted_at.is_(None))
    if filters.view == "active":
        stmt = stmt.where(Task.is_done.is_(False))
    elif filters.view == "done":
        stmt = stmt.where(Task.is_done.is_(True))
    if filters.task_type:
        stmt = stmt.where(Task.task_type == filters.task_type.value)
    if include_deal_client is not None:
        deal_ids = select(Deal.id).where(
            Deal.client_id == include_deal_client,
            Deal.deleted_at.is_(None),
        )
        stmt = stmt.where(
            or_(
                Task.client_id == include_deal_client,
                Task.deal_id.in_(deal_ids),
            )
        )
    elif filters.client_id:
        stmt = stmt.where(Task.client_id == filters.client_id)
    if filters.deal_id:
        stmt = stmt.where(Task.deal_id == filters.deal_id)
    if filters.due_from:
        start, _ = local_day_bounds(filters.due_from)
        stmt = stmt.where(Task.due_at >= start)
    if filters.due_to:
        _, end = local_day_bounds(filters.due_to)
        stmt = stmt.where(Task.due_at <= end)
    if filters.due_state:
        now = utc_now()
        start, end = local_day_bounds()
        if filters.due_state == "overdue":
            stmt = stmt.where(
                Task.is_done.is_(False),
                Task.due_at.is_not(None),
                Task.due_at < now,
            )
        elif filters.due_state == "today":
            stmt = stmt.where(
                Task.is_done.is_(False),
                Task.due_at >= start,
                Task.due_at <= end,
            )
        elif filters.due_state == "upcoming":
            stmt = stmt.where(
                Task.is_done.is_(False),
                Task.due_at > end,
            )
        elif filters.due_state == "no_due":
            stmt = stmt.where(
                Task.is_done.is_(False),
                Task.due_at.is_(None),
            )
    stmt = _apply_q(stmt, filters.q)
    return stmt


def list_tasks(
    db: Session,
    filters: TaskFilters,
    *,
    include_deal_client: int | None = None,
) -> Page[TaskListItem]:
    stmt = _base_list_stmt(
        filters,
        include_deal_client=include_deal_client,
    )
    stmt = apply_sort(stmt, filters.sort, filters.order, SORT_WHITELIST)
    total = db.scalar(
        select(func.count()).select_from(stmt.subquery())
    ) or 0
    pages = max(1, (total + filters.page_size - 1) // filters.page_size)
    page = min(filters.page, pages) if total else 1
    rows = db.scalars(
        stmt.options(
            joinedload(Task.client),
            joinedload(Task.deal),
        )
        .offset((page - 1) * filters.page_size)
        .limit(filters.page_size)
    ).unique().all()
    items = [_to_list_item(t) for t in rows]
    return Page(
        items=items,
        total=total,
        page=page,
        page_size=filters.page_size,
        pages=pages if total else 1,
    )


def list_tasks_all(
    db: Session,
    filters: TaskFilters,
) -> list[Task]:
    stmt = _base_list_stmt(filters)
    stmt = apply_sort(stmt, filters.sort, filters.order, SORT_WHITELIST)
    return list(
        db.scalars(
            stmt.options(
                joinedload(Task.client),
                joinedload(Task.deal),
            )
        ).unique().all()
    )


def _to_list_item(task: Task) -> TaskListItem:
    client_name = None
    if task.client and task.client.deleted_at is None:
        client_name = task.client.name
    deal_title = None
    if task.deal and task.deal.deleted_at is None:
        deal_title = task.deal.title
    return TaskListItem(
        id=task.id,
        title=task.title,
        task_type=TaskType(task.task_type),
        due_at=task.due_at,
        all_day=task.all_day,
        is_done=task.is_done,
        client_id=task.client_id,
        client_name=client_name,
        deal_id=task.deal_id,
        deal_title=deal_title,
        due_state=due_state_for(task),
    )


def reminder_summary(db: Session) -> ReminderSummary:
    now = utc_now()
    start, end = local_day_bounds()
    week_end = end + timedelta(days=7)
    base = select(Task).where(
        Task.deleted_at.is_(None),
        Task.is_done.is_(False),
        Task.due_at.is_not(None),
    )
    overdue = db.scalar(
        select(func.count()).select_from(
            base.where(Task.due_at < now).subquery()
        )
    ) or 0
    today = db.scalar(
        select(func.count()).select_from(
            base.where(
                Task.due_at >= start,
                Task.due_at <= end,
                Task.due_at >= now,
            ).subquery()
        )
    ) or 0
    upcoming = db.scalar(
        select(func.count()).select_from(
            base.where(
                Task.due_at > end,
                Task.due_at <= week_end,
            ).subquery()
        )
    ) or 0
    return ReminderSummary(
        overdue=overdue,
        today=today,
        upcoming_7d=upcoming,
    )


def dashboard_tasks(db: Session) -> dict[str, list[TaskRead]]:
    now = utc_now()
    start, end = local_day_bounds()
    week_end = end + timedelta(days=7)
    active = db.scalars(
        select(Task)
        .where(
            Task.deleted_at.is_(None),
            Task.is_done.is_(False),
            Task.due_at.is_not(None),
        )
        .options(joinedload(Task.client), joinedload(Task.deal))
        .order_by(Task.due_at.asc())
    ).unique().all()
    overdue, today, upcoming = [], [], []
    for task in active:
        due = task.due_at
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        item = _to_read(db, task)
        if due < now:
            overdue.append(item)
        elif start <= due <= end:
            today.append(item)
        elif end < due <= week_end:
            upcoming.append(item)
    return {
        "overdue": overdue,
        "today": today,
        "upcoming": upcoming,
    }
