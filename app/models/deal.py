"""Deal model."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class Deal(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "deals"
    __table_args__ = (
        Index("ix_deals_deleted_status", "deleted_at", "status"),
        Index("ix_deals_client_id", "client_id"),
        Index("ix_deals_search_text", "search_text"),
        Index("ix_deals_updated_at", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="new",
    )
    amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_close_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    lost_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    client = relationship("Client", back_populates="deals")
    orders = relationship("Order", back_populates="deal")
    tasks = relationship("Task", back_populates="deal")
