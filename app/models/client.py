"""Client model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class Client(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "clients"
    __table_args__ = (
        Index(
            "ix_clients_deleted_archived_status",
            "deleted_at",
            "is_archived",
            "status",
        ),
        Index("ix_clients_search_text", "search_text"),
        Index("ix_clients_updated_at", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    client_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="company",
    )
    contact_person: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="lead",
    )
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    deals = relationship("Deal", back_populates="client")
    orders = relationship("Order", back_populates="client")
    tasks = relationship("Task", back_populates="client")
