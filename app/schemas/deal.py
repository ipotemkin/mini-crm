"""Deal schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import DealStatus
from app.schemas.common import empty_to_none


class DealCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    client_id: int | None = None
    status: DealStatus = DealStatus.NEW
    amount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=2,
    )
    expected_close_date: date | None = None
    lost_reason: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("lost_reason", "description", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            return empty_to_none(value)
        return value


class DealUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    client_id: int | None = None
    status: DealStatus | None = None
    amount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=2,
    )
    expected_close_date: date | None = None
    lost_reason: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("lost_reason", "description", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            return empty_to_none(value)
        return value


class DealStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: DealStatus
    lost_reason: str | None = Field(default=None, max_length=500)


class DealClientUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: int


class DealRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    client_id: int | None
    client_name: str | None = None
    client_archived: bool = False
    client_deleted: bool = False
    status: DealStatus
    amount: Decimal | None
    expected_close_date: date | None
    closed_at: datetime | None
    lost_reason: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime


class DealListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    client_id: int | None
    client_name: str | None = None
    status: DealStatus
    amount: Decimal | None
    expected_close_date: date | None
    updated_at: datetime


class DealFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str | None = None
    status: list[DealStatus] | None = None
    group: Literal["open", "closed", "all"] = "open"
    client_id: int | None = None
    no_client: bool = False
    amount_min: Decimal | None = Field(default=None, ge=0)
    amount_max: Decimal | None = Field(default=None, ge=0)
    close_from: date | None = None
    close_to: date | None = None
    sort: str = "updated_at"
    order: Literal["asc", "desc"] = "desc"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)
