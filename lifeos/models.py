from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class LifeNodeBase(SQLModel):
    content: str
    tags: str


class LifeNode(LifeNodeBase):
    id: str = Field(primary_key=True)


class EventBase(LifeNodeBase):
    start_time: datetime
    end_time: datetime
    is_fixed: bool = False


class Event(EventBase, table=True):
    id: str = Field(primary_key=True)


class EventCreate(EventBase):
    id: str


class TaskBase(LifeNodeBase):
    status: str
    deadline: Optional[datetime] = None
    estimated_duration_minutes: int
    dependency_ids: str


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
