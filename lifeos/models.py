from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import field_validator, model_validator
from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class TaskStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class DiagnosticSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class AuditMixin(SQLModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow},
    )


class LifeNodePayload(SQLModel):
    content: str
    tags: list[str] = Field(default_factory=list)

    @field_validator("content")
    @classmethod
    def content_must_not_be_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("content must not be empty")
        return stripped

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("tags must be a list")

        normalized: list[str] = []
        for tag in value:
            if not isinstance(tag, str):
                raise ValueError("tags must only contain strings")
            stripped = tag.strip()
            if not stripped:
                raise ValueError("tags must not contain empty values")
            normalized.append(stripped)
        return normalized


class ProjectBase(SQLModel):
    name: str
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be empty")
        return stripped


class Project(ProjectBase, AuditMixin, table=True):
    id: str = Field(primary_key=True)


class EventBase(LifeNodePayload):
    start_time: datetime
    end_time: datetime
    is_fixed: bool = False
    project_id: Optional[str] = Field(default=None, foreign_key="project.id")

    @model_validator(mode="after")
    def validate_time_range(self) -> "EventBase":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class Event(EventBase, AuditMixin, table=True):
    id: str = Field(primary_key=True)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class EventCreate(EventBase):
    id: str


class EventUpdate(EventBase):
    pass


class EventRead(EventBase, AuditMixin):
    id: str


class TaskBase(LifeNodePayload):
    status: TaskStatus = TaskStatus.TODO
    deadline: Optional[datetime] = None
    estimated_duration_minutes: int
    project_id: Optional[str] = Field(default=None, foreign_key="project.id")

    @field_validator("estimated_duration_minutes")
    @classmethod
    def estimated_duration_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("estimated_duration_minutes must be greater than 0")
        return value


class Task(TaskBase, AuditMixin, table=True):
    id: str = Field(primary_key=True)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    completed_at: Optional[datetime] = None


class TaskCreate(TaskBase):
    id: str
    dependency_ids: list[str] = Field(default_factory=list)

    @field_validator("dependency_ids", mode="before")
    @classmethod
    def validate_dependency_ids(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("dependency_ids must be a list")

        normalized: list[str] = []
        for dependency_id in value:
            if not isinstance(dependency_id, str):
                raise ValueError("dependency_ids must only contain strings")
            stripped = dependency_id.strip()
            if not stripped:
                raise ValueError("dependency_ids must not contain empty values")
            normalized.append(stripped)

        if len(set(normalized)) != len(normalized):
            raise ValueError("dependency_ids must be unique")

        return normalized

    @model_validator(mode="after")
    def task_must_not_depend_on_itself(self) -> "TaskCreate":
        if self.id in self.dependency_ids:
            raise ValueError("task cannot depend on itself")
        return self


class TaskRead(TaskBase, AuditMixin):
    id: str
    completed_at: Optional[datetime] = None
    dependency_ids: list[str] = Field(default_factory=list)


class TaskUpdate(TaskBase):
    dependency_ids: list[str] = Field(default_factory=list)

    @field_validator("dependency_ids", mode="before")
    @classmethod
    def validate_dependency_ids(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("dependency_ids must be a list")

        normalized: list[str] = []
        for dependency_id in value:
            if not isinstance(dependency_id, str):
                raise ValueError("dependency_ids must only contain strings")
            stripped = dependency_id.strip()
            if not stripped:
                raise ValueError("dependency_ids must not contain empty values")
            normalized.append(stripped)

        if len(set(normalized)) != len(normalized):
            raise ValueError("dependency_ids must be unique")

        return normalized


class TaskDependency(SQLModel, table=True):
    predecessor_task_id: str = Field(foreign_key="task.id", primary_key=True)
    successor_task_id: str = Field(foreign_key="task.id", primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Routine(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    task_template: str
    project_id: Optional[str] = Field(default=None, foreign_key="project.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow},
    )


class RecurringRule(SQLModel, table=True):
    id: str = Field(primary_key=True)
    routine_id: str = Field(foreign_key="routine.id")
    cadence: str
    interval: int = 1
    start_at: datetime
    end_at: Optional[datetime] = None

    @field_validator("interval")
    @classmethod
    def interval_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("interval must be greater than 0")
        return value


class Diagnostic(SQLModel):
    code: str
    severity: DiagnosticSeverity
    message: str
    start: datetime
    end: Optional[datetime] = None
    event_id: Optional[str] = None
    hint: Optional[str] = None


class LintSummary(SQLModel):
    severity_counts: dict[DiagnosticSeverity, int] = Field(default_factory=dict)
    top_blocking_issues: list[Diagnostic] = Field(default_factory=list)


class LintEventInput(SQLModel):
    id: str
    start_time: datetime
    end_time: datetime
    project_id: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    dependency_ids: list[str] = Field(default_factory=list)
    deadline: Optional[datetime] = None
    estimated_duration_minutes: Optional[int] = None


class LintRequest(SQLModel):
    events: list[LintEventInput]


class LintResponse(SQLModel):
    diagnostics: list[Diagnostic]
    summary: LintSummary
