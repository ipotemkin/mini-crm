"""Fixed status and type enumerations for MVP."""

from enum import StrEnum


class ClientType(StrEnum):
    PERSON = "person"
    COMPANY = "company"


class ClientStatus(StrEnum):
    LEAD = "lead"
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOST = "lost"


class DealStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"


class OrderStatus(StrEnum):
    NEW = "new"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskType(StrEnum):
    CALL = "call"
    MEETING = "meeting"
    EMAIL = "email"
    TODO = "todo"
    OTHER = "other"


CLIENT_STATUS_LABELS = {
    ClientStatus.LEAD: "Потенциальный",
    ClientStatus.ACTIVE: "Активный",
    ClientStatus.INACTIVE: "Неактивный",
    ClientStatus.LOST: "Потерян",
}

CLIENT_TYPE_LABELS = {
    ClientType.PERSON: "Физ. лицо",
    ClientType.COMPANY: "Компания",
}

DEAL_STATUS_LABELS = {
    DealStatus.NEW: "Новая",
    DealStatus.IN_PROGRESS: "В работе",
    DealStatus.PROPOSAL: "КП отправлено",
    DealStatus.NEGOTIATION: "Переговоры",
    DealStatus.WON: "Успешно закрыта",
    DealStatus.LOST: "Проиграна",
}

DEAL_OPEN_STATUSES = {
    DealStatus.NEW,
    DealStatus.IN_PROGRESS,
    DealStatus.PROPOSAL,
    DealStatus.NEGOTIATION,
}

DEAL_CLOSED_STATUSES = {DealStatus.WON, DealStatus.LOST}

ORDER_STATUS_LABELS = {
    OrderStatus.NEW: "Новый",
    OrderStatus.CONFIRMED: "Подтверждён",
    OrderStatus.IN_PROGRESS: "В исполнении",
    OrderStatus.COMPLETED: "Выполнен",
    OrderStatus.CANCELLED: "Отменён",
}

TASK_TYPE_LABELS = {
    TaskType.CALL: "Звонок",
    TaskType.MEETING: "Встреча",
    TaskType.EMAIL: "Письмо",
    TaskType.TODO: "Дело",
    TaskType.OTHER: "Прочее",
}

DUE_STATE_LABELS = {
    "overdue": "Просрочена",
    "today": "Сегодня",
    "upcoming": "Предстоит",
    "no_due": "Без срока",
    "done": "Выполнена",
}
