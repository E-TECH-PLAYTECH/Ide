from __future__ import annotations

from collections import defaultdict
from typing import List

from fastapi import Depends, FastAPI, HTTPException, status
from sqlmodel import Session, select

from .database import create_db_and_tables, get_session
from .linter import lint_events
from .models import (
    Event,
    EventCreate,
    EventRead,
    LintRequest,
    LintResponse,
    Task,
    TaskCreate,
    TaskDependency,
    TaskRead,
)

app = FastAPI(title="LifeOS")


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/events", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def create_event(
    event: EventCreate, session: Session = Depends(get_session)
) -> Event:
    existing = session.get(Event, event.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Event with this id already exists",
        )
    db_event = Event.model_validate(event)
    session.add(db_event)
    session.commit()
    session.refresh(db_event)
    return db_event


@app.get("/events", response_model=List[EventRead])
def list_events(session: Session = Depends(get_session)) -> list[Event]:
    statement = select(Event).order_by(Event.start_time)
    return list(session.exec(statement).all())


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
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Adding dependency from {dependency_id} to {new_task_id} creates a cycle",
            )


@app.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(task: TaskCreate, session: Session = Depends(get_session)) -> TaskRead:
    existing = session.get(Task, task.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task with this id already exists",
        )

    missing_dependency_ids = [
        dependency_id
        for dependency_id in task.dependency_ids
        if session.get(Task, dependency_id) is None
    ]
    if missing_dependency_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown dependency task ids: {', '.join(missing_dependency_ids)}",
        )

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
    return TaskRead.model_validate(
        db_task,
        update={"dependency_ids": task.dependency_ids},
    )


@app.get("/tasks", response_model=List[TaskRead])
def list_tasks(session: Session = Depends(get_session)) -> list[TaskRead]:
    tasks = list(session.exec(select(Task).order_by(Task.deadline)).all())
    task_ids = [task.id for task in tasks]

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
            update={"dependency_ids": dependencies_by_task.get(task.id, [])},
        )
        for task in tasks
    ]


@app.post("/lint", response_model=LintResponse)
async def lint(request: LintRequest) -> LintResponse:
    diagnostics = lint_events(request.events)
    return LintResponse(diagnostics=diagnostics)


@app.get("/lint", response_model=LintResponse)
def lint_from_db(session: Session = Depends(get_session)) -> LintResponse:
    statement = select(Event)
    events = list(session.exec(statement).all())
    diagnostics = lint_events(events)
    return LintResponse(diagnostics=diagnostics)
