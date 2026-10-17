"""Export column definitions and row builders."""

from __future__ import annotations

from typing import Any, Callable

from app.core.enums import (
    CLIENT_STATUS_LABELS,
    CLIENT_TYPE_LABELS,
    DEAL_STATUS_LABELS,
    DUE_STATE_LABELS,
    ORDER_STATUS_LABELS,
    TASK_TYPE_LABELS,
    ClientStatus,
    ClientType,
    DealStatus,
    OrderStatus,
    TaskType,
)
from app.core.money import from_kopecks
from app.core.timeutils import format_date, format_datetime
from app.services.tasks import due_state_for

ENTITY_LABELS = {
    "clients": "Клиенты",
    "deals": "Сделки",
    "orders": "Заказы",
    "tasks": "Задачи",
    "search": "Поиск",
}

CLIENT_HEADERS = [
    "ID",
    "Имя/название",
    "Тип",
    "Контактное лицо",
    "Телефон",
    "Email",
    "Статус",
    "Источник",
    "В архиве",
    "Открытых сделок",
    "Невыполненных задач",
    "Создан",
    "Изменён",
    "Заметки",
]

DEAL_HEADERS = [
    "ID",
    "Название",
    "Клиент",
    "ID клиента",
    "Статус",
    "Сумма",
    "Плановая дата закрытия",
    "Дата закрытия",
    "Причина проигрыша",
    "Создана",
    "Изменена",
    "Описание",
]

ORDER_HEADERS = [
    "ID",
    "Номер",
    "Название",
    "Клиент",
    "ID клиента",
    "Сделка",
    "ID сделки",
    "Статус",
    "Сумма",
    "Дата заказа",
    "Плановая дата исполнения",
    "Создан",
    "Комментарий",
]

TASK_HEADERS = [
    "ID",
    "Название",
    "Тип",
    "Срок",
    "Состояние срока",
    "Выполнена",
    "Дата выполнения",
    "Клиент",
    "ID клиента",
    "Сделка",
    "ID сделки",
    "Создана",
    "Описание",
]

SEARCH_HEADERS = [
    "Тип записи",
    "ID",
    "Название",
    "Статус",
    "Клиент",
    "Изменён",
]


def _safe(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@"}:
        return "'" + value
    return value


def _yes_no(flag: bool) -> str:
    return "Да" if flag else "Нет"


def _money(kopecks: int | None) -> float | str:
    amount = from_kopecks(kopecks)
    if amount is None:
        return ""
    return float(amount)


def client_row(client, open_deals: int = 0, open_tasks: int = 0) -> list:
    return [
        client.id,
        _safe(client.name),
        CLIENT_TYPE_LABELS.get(ClientType(client.client_type), ""),
        _safe(client.contact_person),
        _safe(client.phone),
        _safe(client.email),
        CLIENT_STATUS_LABELS.get(ClientStatus(client.status), ""),
        _safe(client.source),
        _yes_no(client.is_archived),
        open_deals,
        open_tasks,
        format_datetime(client.created_at),
        format_datetime(client.updated_at),
        _safe(client.notes),
    ]


def deal_row(deal) -> list:
    client_name = ""
    if deal.client and deal.client.deleted_at is None:
        client_name = deal.client.name
    elif deal.client_id:
        client_name = "Клиент удалён"
    return [
        deal.id,
        _safe(deal.title),
        _safe(client_name),
        deal.client_id or "",
        DEAL_STATUS_LABELS.get(DealStatus(deal.status), ""),
        _money(deal.amount),
        format_date(deal.expected_close_date),
        format_datetime(deal.closed_at),
        _safe(deal.lost_reason),
        format_datetime(deal.created_at),
        format_datetime(deal.updated_at),
        _safe(deal.description),
    ]


def order_row(order) -> list:
    client_name = ""
    if order.client and order.client.deleted_at is None:
        client_name = order.client.name
    deal_title = ""
    if order.deal and order.deal.deleted_at is None:
        deal_title = order.deal.title
    return [
        order.id,
        order.number,
        _safe(order.title),
        _safe(client_name),
        order.client_id or "",
        _safe(deal_title),
        order.deal_id or "",
        ORDER_STATUS_LABELS.get(OrderStatus(order.status), ""),
        _money(order.amount),
        format_date(order.order_date),
        format_date(order.due_date),
        format_datetime(order.created_at),
        _safe(order.comment),
    ]


def task_row(task) -> list:
    client_name = ""
    if task.client and task.client.deleted_at is None:
        client_name = task.client.name
    deal_title = ""
    if task.deal and task.deal.deleted_at is None:
        deal_title = task.deal.title
    state = due_state_for(task)
    return [
        task.id,
        _safe(task.title),
        TASK_TYPE_LABELS.get(TaskType(task.task_type), ""),
        format_datetime(task.due_at),
        DUE_STATE_LABELS.get(state, state),
        _yes_no(task.is_done),
        format_datetime(task.done_at),
        _safe(client_name),
        task.client_id or "",
        _safe(deal_title),
        task.deal_id or "",
        format_datetime(task.created_at),
        _safe(task.description),
    ]


HEADERS: dict[str, list[str]] = {
    "clients": CLIENT_HEADERS,
    "deals": DEAL_HEADERS,
    "orders": ORDER_HEADERS,
    "tasks": TASK_HEADERS,
    "search": SEARCH_HEADERS,
}

ROW_BUILDERS: dict[str, Callable] = {
    "clients": client_row,
    "deals": deal_row,
    "orders": order_row,
    "tasks": task_row,
}
