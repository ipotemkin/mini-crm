"""Task schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import TaskType
from app.schemas.common import empty_to_none


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    task_type: TaskType = TaskType.TODO
    description: str | None = Field(default=None, max_length=5000)
    due_at: datetime | None = None
    due_date: date | None = None
    all_day: bool = False
    client_id: int | None = None
    deal_id: int | None = None

    @field_validator("description", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            return empty_to_none(value)
        return value


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    task_type: TaskType | None = None
    description: str | None = Field(default=None, max_length=5000)
    due_at: datetime | None = None
    due_date: date | None = None
    all_day: bool | None = None
    client_id: int | None = None
    deal_id: int | None = None
    clear_due: bool = False

    @field_validator("description", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            return empty_to_none(value)
        return value


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    task_type: TaskType
    description: str | None
    due_at: datetime | None
    all_day: bool
    is_done: bool
    done_at: datetime | None
    client_id: int | None
    client_name: str | None = None
    deal_id: int | None
    deal_title: str | None = None
    due_state: str = "no_due"
    created_at: datetime
    updated_at: datetime


class TaskListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    task_type: TaskType
    due_at: datetime | None
    all_day: bool
    is_done: bool
    client_id: int | None
    client_name: str | None = None
    deal_id: int | None
    deal_title: str | None = None
    due_state: str = "no_due"


class TaskFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str | None = None
    view: Literal["active", "done", "all"] = "active"
    due_state: (
        Literal["overdue", "today", "upcoming", "no_due"] | None
    ) = None
    task_type: TaskType | None = None
    client_id: int | None = None
    deal_id: int | None = None
    due_from: date | None = None
    due_to: date | None = None
    sort: str = "due_at"
    order: Literal["asc", "desc"] = "asc"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)


class ReminderSummary(BaseModel):
    overdue: int
    today: int
    upcoming_7d: int
