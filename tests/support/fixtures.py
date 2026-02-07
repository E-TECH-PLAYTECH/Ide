from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LintEventFixture:
    id: str
    start_time: datetime
    end_time: datetime
    project_id: str | None = None
    tags: list[str] = field(default_factory=list)
    dependency_ids: list[str] = field(default_factory=list)
    deadline: datetime | None = None
    estimated_duration_minutes: int | None = None


def build_lint_event(
    event_id: str,
    start_hour: int,
    start_minute: int,
    end_hour: int,
    end_minute: int,
    **overrides: object,
) -> LintEventFixture:
    return LintEventFixture(
        id=event_id,
        start_time=datetime(2024, 1, 1, start_hour, start_minute),
        end_time=datetime(2024, 1, 1, end_hour, end_minute),
        **overrides,
    )


def build_event_payload(
    event_id: str,
    start_time: str,
    end_time: str,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": event_id,
        "content": f"Event {event_id}",
        "tags": ["default"],
        "start_time": start_time,
        "end_time": end_time,
        "is_fixed": False,
        "project_id": None,
    }
    payload.update(overrides)
    return payload


def build_task_payload(
    task_id: str,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": task_id,
        "content": f"Task {task_id}",
        "tags": ["default"],
        "status": "TODO",
        "deadline": "2024-01-20T10:00:00",
        "estimated_duration_minutes": 30,
        "project_id": None,
        "dependency_ids": [],
    }
    payload.update(overrides)
    return payload


def build_project_scenario(project_id: str) -> tuple[dict[str, object], dict[str, object]]:
    predecessor = build_task_payload(
        task_id=f"{project_id}-dep",
        project_id=project_id,
        deadline="2024-01-20T09:00:00",
    )
    successor = build_task_payload(
        task_id=f"{project_id}-task",
        project_id=project_id,
        deadline="2024-01-20T10:00:00",
        dependency_ids=[predecessor["id"]],
    )
    return predecessor, successor
