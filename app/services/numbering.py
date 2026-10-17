"""Order number generation: ORD-000001."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.order import Order


def next_order_number(db: Session) -> str:
    stmt = select(func.count()).select_from(Order)
    # Count all rows including soft-deleted so numbers are not reused
    total = db.scalar(stmt) or 0
    return f"ORD-{total + 1:06d}"
