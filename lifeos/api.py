from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import logging
import time
from typing import Any, List, Optional
from uuid import uuid4

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from .database import database_is_reachable, get_session
from .linter import lint_events
from .logging_utils import configure_logging, log_event
from .metrics import metrics
from .models import (
    Event,
    EventCreate,
    EventRead,
    EventUpdate,
    LintRequest,
    LintResponse,
    Task,
    TaskCreate,
    TaskDependency,
    TaskRead,
    TaskStatus,
    TaskUpdate,
)

ERROR_EXAMPLE = {
    "application/json": {
        "example": {
            "error": {
                "code": "not_found",
                "message": "Task not found",
                "details": {"resource": "task", "id": "task-123"},
            }
        }
    }
}

app = FastAPI(title="LifeOS")

configure_logging()
logger = logging.getLogger(__name__)



def _error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        payload["error"]["details"] = details
    return payload


def _raise_http_error(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=_error_payload(code=code, message=message, details=details),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        payload = exc.detail
    else:
        payload = _error_payload(code="http_error", message=str(exc.detail))
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_payload(
            code="validation_error",
            message="Validation failed",
            details={"issues": jsonable_encoder(exc.errors())},
        ),
    )


@app.middleware("http")
async def request_context_middleware(request: Request, call_next: Any) -> JSONResponse:
    start = time.perf_counter()
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id

    log_event(
        logger,
        "request.started",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start) * 1000, 3)
    response.headers["X-Request-ID"] = request_id
    metrics.record_request(response.status_code, duration_ms)
    log_event(
        logger,
        "request.completed",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response


@app.get("/health/live", summary="Liveness check endpoint")
async def liveness_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", summary="Readiness check endpoint")
async def readiness_check() -> JSONResponse:
    if database_is_reachable():
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ready"})
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"status": "not_ready"})


@app.post(
    "/events",
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an event",
    responses={409: {"description": "Conflict", "content": ERROR_EXAMPLE}},
)
def create_event(
    event: EventCreate = Body(
        ...,
        example={
            "id": "event-1",
            "content": "Focus block",
            "tags": ["deep-work"],
            "start_time": "2026-01-12T09:00:00",
            "end_time": "2026-01-12T10:00:00",
            "is_fixed": True,
            "project_id": "project-1",
        },
    ),
    session: Session = Depends(get_session),
) -> Event:
    existing = session.get(Event, event.id)
    if existing:
        _raise_http_error(
            status_code=status.HTTP_409_CONFLICT,
            code="conflict",
            message="Event with this id already exists",
            details={"resource": "event", "id": event.id},
        )
    db_event = Event.model_validate(event)
    session.add(db_event)
    session.commit()
    session.refresh(db_event)
    return db_event


@app.get(
    "/events",
    response_model=List[EventRead],
    summary="List events with filtering and pagination",
)
def list_events(
    start_from: Optional[datetime] = Query(None, description="Minimum start_time", example="2026-01-12T00:00:00"),
    start_to: Optional[datetime] = Query(None, description="Maximum start_time", example="2026-01-12T23:59:59"),
    end_from: Optional[datetime] = Query(None, description="Minimum end_time"),
    end_to: Optional[datetime] = Query(None, description="Maximum end_time"),
    project_id: Optional[str] = Query(None, description="Filter by project id"),
    tags: list[str] = Query(default=[], description="Filter by tags (match any)"),
    is_fixed: Optional[bool] = Query(None, description="Filter fixed vs flexible events"),
    limit: int = Query(50, ge=1, le=200, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Records to skip"),
    session: Session = Depends(get_session),
) -> list[Event]:
    statement = select(Event)
    if start_from:
        statement = statement.where(Event.start_time >= start_from)
    if start_to:
        statement = statement.where(Event.start_time <= start_to)
    if end_from:
        statement = statement.where(Event.end_time >= end_from)
    if end_to:
        statement = statement.where(Event.end_time <= end_to)
    if project_id:
        statement = statement.where(Event.project_id == project_id)
    if is_fixed is not None:
        statement = statement.where(Event.is_fixed == is_fixed)
    if tags:
        statement = statement.where(Event.tags.contains(tags))

    statement = statement.order_by(Event.start_time, Event.id).limit(limit).offset(offset)
    return list(session.exec(statement).all())


@app.get("/events/{event_id}", response_model=EventRead, summary="Get an event by id")
def get_event(event_id: str, session: Session = Depends(get_session)) -> Event:
    event = session.get(Event, event_id)
    if not event:
        _raise_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message="Event not found",
            details={"resource": "event", "id": event_id},
        )
    return event


@app.put("/events/{event_id}", response_model=EventRead, summary="Update an event by id")
def update_event(
    event_id: str,
    event_update: EventUpdate = Body(
        ...,
        example={
            "content": "Updated focus block",
            "tags": ["planning"],
            "start_time": "2026-01-12T10:00:00",
            "end_time": "2026-01-12T11:00:00",
            "is_fixed": False,
            "project_id": "project-1",
        },
    ),
    session: Session = Depends(get_session),
) -> Event:
    db_event = session.get(Event, event_id)
    if not db_event:
        _raise_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message="Event not found",
            details={"resource": "event", "id": event_id},
        )

    for field, value in event_update.model_dump().items():
        setattr(db_event, field, value)

    session.add(db_event)
    session.commit()
    session.refresh(db_event)
    return db_event


@app.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an event by id")
def delete_event(event_id: str, session: Session = Depends(get_session)) -> None:
    db_event = session.get(Event, event_id)
    if not db_event:
        _raise_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message="Event not found",
            details={"resource": "event", "id": event_id},
        )
    session.delete(db_event)
    session.commit()


def _assert_no_circular_dependencies(
    session: Session, new_task_id: str, dependency_ids: list[str]
) -> None:
    if not dependency_ids:
        return

    edges = session.exec(select(TaskDependency)).all()
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        adjacency[edge.predecessor_task_id].add(edge.successor_task_id)

    def has_path(source: str, target: str) -> bool:
        stack = [source]
        visited: set[str] = set()
        while stack:
            node = stack.pop()
            if node == target:
                return True
            if node in visited:
                continue
            visited.add(node)
            stack.extend(adjacency.get(node, set()))
        return False

    for dependency_id in dependency_ids:
        if has_path(new_task_id, dependency_id):
            _raise_http_error(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="validation_error",
                message=f"Adding dependency from {dependency_id} to {new_task_id} creates a cycle",
            )


def _assert_dependencies_exist(session: Session, dependency_ids: list[str]) -> None:
    missing_dependency_ids = [
        dependency_id
        for dependency_id in dependency_ids
        if session.get(Task, dependency_id) is None
    ]
    if missing_dependency_ids:
        _raise_http_error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="validation_error",
            message="Unknown dependency task ids",
            details={"dependency_ids": missing_dependency_ids},
        )


def _build_task_reads(session: Session, tasks: list[Task]) -> list[TaskRead]:
    task_ids = [task.id for task in tasks]
    if not task_ids:
        return []

    dependency_rows = list(
        session.exec(
            select(TaskDependency).where(TaskDependency.successor_task_id.in_(task_ids))
        ).all()
    )

    dependencies_by_task: dict[str, list[str]] = defaultdict(list)
    for dependency in dependency_rows:
        dependencies_by_task[dependency.successor_task_id].append(
            dependency.predecessor_task_id
        )

    return [
        TaskRead.model_validate(
            task,
            update={"dependency_ids": sorted(dependencies_by_task.get(task.id, []))},
        )
        for task in tasks
    ]


@app.post(
    "/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task",
)
def create_task(
    task: TaskCreate = Body(
        ...,
        example={
            "id": "task-1",
            "content": "Write plan",
            "tags": ["work"],
            "status": "TODO",
            "deadline": "2026-01-20T17:00:00",
            "estimated_duration_minutes": 90,
            "project_id": "project-1",
            "dependency_ids": [],
        },
    ),
    session: Session = Depends(get_session),
) -> TaskRead:
    existing = session.get(Task, task.id)
    if existing:
        _raise_http_error(
            status_code=status.HTTP_409_CONFLICT,
            code="conflict",
            message="Task with this id already exists",
            details={"resource": "task", "id": task.id},
        )

    _assert_dependencies_exist(session, task.dependency_ids)
    _assert_no_circular_dependencies(session, task.id, task.dependency_ids)

    db_task = Task.model_validate(task.model_dump(exclude={"dependency_ids"}))
    session.add(db_task)
    for dependency_id in task.dependency_ids:
        session.add(
            TaskDependency(
                predecessor_task_id=dependency_id,
                successor_task_id=task.id,
            )
        )
    session.commit()
    session.refresh(db_task)
    return TaskRead.model_validate(db_task, update={"dependency_ids": task.dependency_ids})


@app.get("/tasks", response_model=List[TaskRead], summary="List tasks with filtering and pagination")
def list_tasks(
    status_filter: Optional[TaskStatus] = Query(None, alias="status", description="Task status"),
    deadline_from: Optional[datetime] = Query(None, description="Minimum deadline"),
    deadline_to: Optional[datetime] = Query(None, description="Maximum deadline"),
    project_id: Optional[str] = Query(None, description="Filter by project id"),
    tags: list[str] = Query(default=[], description="Filter by tags (match any)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Records to skip"),
    session: Session = Depends(get_session),
) -> list[TaskRead]:
    statement = select(Task)
    if status_filter:
        statement = statement.where(Task.status == status_filter)
    if deadline_from:
        statement = statement.where(Task.deadline >= deadline_from)
    if deadline_to:
        statement = statement.where(Task.deadline <= deadline_to)
    if project_id:
        statement = statement.where(Task.project_id == project_id)
    if tags:
        statement = statement.where(Task.tags.contains(tags))

    statement = statement.order_by(Task.deadline.is_(None), Task.deadline, Task.id).limit(limit).offset(offset)
    tasks = list(session.exec(statement).all())
    return _build_task_reads(session, tasks)


@app.get("/tasks/{task_id}", response_model=TaskRead, summary="Get a task by id")
def get_task(task_id: str, session: Session = Depends(get_session)) -> TaskRead:
    task = session.get(Task, task_id)
    if not task:
        _raise_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message="Task not found",
            details={"resource": "task", "id": task_id},
        )
    return _build_task_reads(session, [task])[0]


@app.put("/tasks/{task_id}", response_model=TaskRead, summary="Update a task by id")
def update_task(
    task_id: str,
    task_update: TaskUpdate,
    session: Session = Depends(get_session),
) -> TaskRead:
    db_task = session.get(Task, task_id)
    if not db_task:
        _raise_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message="Task not found",
            details={"resource": "task", "id": task_id},
        )

    if task_id in task_update.dependency_ids:
        _raise_http_error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="validation_error",
            message="task cannot depend on itself",
        )

    _assert_dependencies_exist(session, task_update.dependency_ids)

    existing_dependencies = list(
        session.exec(
            select(TaskDependency).where(TaskDependency.successor_task_id == task_id)
        ).all()
    )
    for dependency in existing_dependencies:
        session.delete(dependency)

    _assert_no_circular_dependencies(session, task_id, task_update.dependency_ids)

    task_payload = task_update.model_dump(exclude={"dependency_ids"})
    for field, value in task_payload.items():
        setattr(db_task, field, value)
    session.add(db_task)

    for dependency_id in task_update.dependency_ids:
        session.add(
            TaskDependency(
                predecessor_task_id=dependency_id,
                successor_task_id=task_id,
            )
        )

    session.commit()
    session.refresh(db_task)
    return TaskRead.model_validate(
        db_task,
        update={"dependency_ids": sorted(task_update.dependency_ids)},
    )


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a task by id")
def delete_task(task_id: str, session: Session = Depends(get_session)) -> None:
    db_task = session.get(Task, task_id)
    if not db_task:
        _raise_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message="Task not found",
            details={"resource": "task", "id": task_id},
        )
    dependencies = list(
        session.exec(
            select(TaskDependency).where(
                (TaskDependency.predecessor_task_id == task_id)
                | (TaskDependency.successor_task_id == task_id)
            )
        ).all()
    )
    for dependency in dependencies:
        session.delete(dependency)
    session.delete(db_task)
    session.commit()


@app.get(
    "/tasks/{task_id}/dependencies",
    response_model=list[str],
    summary="List dependencies for a task",
)
def list_task_dependencies(task_id: str, session: Session = Depends(get_session)) -> list[str]:
    if not session.get(Task, task_id):
        _raise_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message="Task not found",
            details={"resource": "task", "id": task_id},
        )
    dependency_rows = list(
        session.exec(
            select(TaskDependency).where(TaskDependency.successor_task_id == task_id)
        ).all()
    )
    return sorted([row.predecessor_task_id for row in dependency_rows])


@app.put(
    "/tasks/{task_id}/dependencies",
    response_model=list[str],
    summary="Replace dependencies for a task",
)
def replace_task_dependencies(
    task_id: str,
    dependency_ids: list[str] = Body(
        ...,
        example=["task-101", "task-202"],
        description="List of predecessor task IDs",
    ),
    session: Session = Depends(get_session),
) -> list[str]:
    if not session.get(Task, task_id):
        _raise_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message="Task not found",
            details={"resource": "task", "id": task_id},
        )
    normalized = [dependency_id.strip() for dependency_id in dependency_ids]
    if any(not dependency_id for dependency_id in normalized):
        _raise_http_error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="validation_error",
            message="dependency_ids must not contain empty values",
        )
    if len(set(normalized)) != len(normalized):
        _raise_http_error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="validation_error",
            message="dependency_ids must be unique",
        )
    if task_id in normalized:
        _raise_http_error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="validation_error",
            message="task cannot depend on itself",
        )

    _assert_dependencies_exist(session, normalized)

    existing = list(
        session.exec(
            select(TaskDependency).where(TaskDependency.successor_task_id == task_id)
        ).all()
    )
    for row in existing:
        session.delete(row)

    _assert_no_circular_dependencies(session, task_id, normalized)

    for dependency_id in normalized:
        session.add(
            TaskDependency(
                predecessor_task_id=dependency_id,
                successor_task_id=task_id,
            )
        )
    session.commit()
    return sorted(normalized)


@app.get(
    "/projects/{project_id}/tasks",
    response_model=List[TaskRead],
    summary="List tasks for a project",
)
def list_project_tasks(
    project_id: str,
    status_filter: Optional[TaskStatus] = Query(None, alias="status", description="Task status"),
    deadline_from: Optional[datetime] = Query(None, description="Minimum deadline"),
    deadline_to: Optional[datetime] = Query(None, description="Maximum deadline"),
    tags: list[str] = Query(default=[], description="Filter by tags (match any)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Records to skip"),
    session: Session = Depends(get_session),
) -> list[TaskRead]:
    statement = select(Task).where(Task.project_id == project_id)
    if status_filter:
        statement = statement.where(Task.status == status_filter)
    if deadline_from:
        statement = statement.where(Task.deadline >= deadline_from)
    if deadline_to:
        statement = statement.where(Task.deadline <= deadline_to)
    if tags:
        statement = statement.where(Task.tags.contains(tags))

    statement = statement.order_by(Task.deadline.is_(None), Task.deadline, Task.id).limit(limit).offset(offset)
    tasks = list(session.exec(statement).all())
    return _build_task_reads(session, tasks)


@app.post("/lint", response_model=LintResponse, summary="Lint events from request body")
async def lint(
    http_request: Request,
    request: LintRequest = Body(
        ...,
        example={
            "events": [
                {
                    "id": "event-1",
                    "start_time": "2026-01-12T09:00:00",
                    "end_time": "2026-01-12T10:00:00",
                }
            ]
        },
    )
) -> LintResponse:
    started = time.perf_counter()
    diagnostics, summary = lint_events(request.events)
    duration_ms = round((time.perf_counter() - started) * 1000, 3)
    metrics.record_lint_execution(duration_ms)
    log_event(
        logger,
        "lint.executed",
        request_id=getattr(http_request.state, "request_id", None),
        source="request",
        event_count=len(request.events),
        diagnostic_count=len(diagnostics),
        duration_ms=duration_ms,
    )
    return LintResponse(diagnostics=diagnostics, summary=summary)


@app.get("/lint", response_model=LintResponse, summary="Lint persisted events")
def lint_from_db(http_request: Request, session: Session = Depends(get_session)) -> LintResponse:
    started = time.perf_counter()
    statement = select(Event)
    events = list(session.exec(statement).all())
    diagnostics, summary = lint_events(events)
    duration_ms = round((time.perf_counter() - started) * 1000, 3)
    metrics.record_lint_execution(duration_ms)
    log_event(
        logger,
        "lint.executed",
        request_id=getattr(http_request.state, "request_id", None),
        source="database",
        event_count=len(events),
        diagnostic_count=len(diagnostics),
        duration_ms=duration_ms,
    )
    return LintResponse(diagnostics=diagnostics, summary=summary)
