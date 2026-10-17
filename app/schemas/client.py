"""Client schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.enums import ClientStatus, ClientType
from app.schemas.common import empty_to_none


class ClientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    client_type: ClientType = ClientType.COMPANY
    contact_person: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    status: ClientStatus = ClientStatus.LEAD
    source: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator(
        "contact_person",
        "phone",
        "source",
        "notes",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            return empty_to_none(value)
        return value


class ClientUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    client_type: ClientType | None = None
    contact_person: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    status: ClientStatus | None = None
    source: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator(
        "contact_person",
        "phone",
        "source",
        "notes",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            return empty_to_none(value)
        return value


class ClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    client_type: ClientType
    contact_person: str | None
    phone: str | None
    email: str | None
    status: ClientStatus
    source: str | None
    notes: str | None
    is_archived: bool
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    open_deals_count: int = 0
    open_tasks_count: int = 0


class ClientListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    client_type: ClientType
    contact_person: str | None
    phone: str | None
    email: str | None
    status: ClientStatus
    is_archived: bool
    updated_at: datetime
    open_deals_count: int = 0
    next_task_due_at: datetime | None = None


class ClientFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str | None = None
    status: list[ClientStatus] | None = None
    archived: Literal["active", "archived", "all"] = "active"
    client_type: ClientType | None = None
    created_from: date | None = None
    created_to: date | None = None
    sort: str = "updated_at"
    order: Literal["asc", "desc"] = "desc"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)


class ClientLookupItem(BaseModel):
    id: int
    name: str
    phone: str | None = None
    email: str | None = None


class DeleteImpact(BaseModel):
    deals: int
    orders: int
    tasks: int
    open_deals: int = 0
    open_tasks: int = 0
