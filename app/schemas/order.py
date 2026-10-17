"""Order schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import OrderStatus
from app.schemas.common import empty_to_none


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    deal_id: int | None = None
    client_id: int | None = None
    status: OrderStatus = OrderStatus.NEW
    amount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=2,
    )
    order_date: date | None = None
    due_date: date | None = None
    comment: str | None = Field(default=None, max_length=5000)

    @field_validator("comment", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            return empty_to_none(value)
        return value


class OrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    deal_id: int | None = None
    client_id: int | None = None
    status: OrderStatus | None = None
    amount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=2,
    )
    order_date: date | None = None
    due_date: date | None = None
    comment: str | None = Field(default=None, max_length=5000)

    @field_validator("comment", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            return empty_to_none(value)
        return value


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    title: str
    deal_id: int | None
    deal_title: str | None = None
    client_id: int | None
    client_name: str | None = None
    status: OrderStatus
    amount: Decimal | None
    order_date: date
    due_date: date | None
    comment: str | None
    created_at: datetime
    updated_at: datetime


class OrderListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    title: str
    deal_id: int | None
    deal_title: str | None = None
    client_id: int | None
    client_name: str | None = None
    status: OrderStatus
    amount: Decimal | None
    order_date: date
    due_date: date | None


class OrderFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str | None = None
    status: list[OrderStatus] | None = None
    client_id: int | None = None
    deal_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None
    sort: str = "order_date"
    order: Literal["asc", "desc"] = "desc"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)
