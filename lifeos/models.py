from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import field_validator, model_validator
from sqlmodel import Field, SQLModel


class LifeNodeBase(SQLModel):
    content: str
    tags: str

    @field_validator("content")
    @classmethod
    def content_must_not_be_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("content must not be empty")
        return stripped


class LifeNode(LifeNodeBase):
    id: str = Field(primary_key=True)


class EventBase(LifeNodeBase):
    start_time: datetime
    end_time: datetime
    is_fixed: bool = False

    @model_validator(mode="after")
    def validate_time_range(self) -> "EventBase":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class Event(EventBase, table=True):
    id: str = Field(primary_key=True)


class EventCreate(EventBase):
    id: str


class TaskBase(LifeNodeBase):
    status: str
    deadline: Optional[datetime] = None
    estimated_duration_minutes: int
    dependency_ids: str

    @field_validator("status")
    @classmethod
    def status_must_not_be_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("status must not be empty")
        return stripped

    @field_validator("estimated_duration_minutes")
    @classmethod
    def estimated_duration_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("estimated_duration_minutes must be greater than 0")
        return value


class Task(TaskBase, table=True):
    id: str = Field(primary_key=True)


class TaskCreate(TaskBase):
    id: str


class Diagnostic(SQLModel):
    severity: str
    message: str
    start: datetime
    end: Optional[datetime] = None
    event_id: Optional[str] = None


class LintRequest(SQLModel):
    events: list[Event]


class LintResponse(SQLModel):
    diagnostics: list[Diagnostic]
