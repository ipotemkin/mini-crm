"""Timezone-aware helpers."""

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from app.config import get_settings


def app_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().app_timezone)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=app_tz()).astimezone(timezone.utc)
    return dt.astimezone(timezone.utc)


def to_local(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(app_tz())


def local_today() -> date:
    return datetime.now(app_tz()).date()


def local_day_bounds(day: date | None = None) -> tuple[datetime, datetime]:
    day = day or local_today()
    start = datetime.combine(day, time.min, tzinfo=app_tz())
    end = datetime.combine(day, time.max, tzinfo=app_tz())
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def all_day_due_at(day: date) -> datetime:
    local = datetime.combine(day, time(23, 59), tzinfo=app_tz())
    return local.astimezone(timezone.utc)


def format_date(value: date | None) -> str:
    if value is None:
        return ""
    return value.strftime("%d.%m.%Y")


def format_datetime(value: datetime | None) -> str:
    local = to_local(value)
    if local is None:
        return ""
    return local.strftime("%d.%m.%Y %H:%M")


def format_money(kopecks: int | None, currency: str | None = None) -> str:
    if kopecks is None:
        return ""
    currency = currency or get_settings().app_currency
    rubles = kopecks / 100
    formatted = f"{rubles:,.2f}".replace(",", " ").replace(".", ",")
    symbol = "₽" if currency == "RUB" else currency
    return f"{formatted} {symbol}"
