from __future__ import annotations

from typing import List

from fastapi import Depends, FastAPI, HTTPException, status
from sqlmodel import Session, select

from .database import create_db_and_tables, get_session
from .linter import lint_events
from .models import (
    Event,
    EventCreate,
    LintRequest,
    LintResponse,
    Task,
    TaskCreate,
)

app = FastAPI(title="LifeOS")


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/events", response_model=Event, status_code=status.HTTP_201_CREATED)
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


@app.get("/events", response_model=List[Event])
def list_events(session: Session = Depends(get_session)) -> list[Event]:
    statement = select(Event).order_by(Event.start_time)
    return list(session.exec(statement).all())


@app.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task(task: TaskCreate, session: Session = Depends(get_session)) -> Task:
    existing = session.get(Task, task.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task with this id already exists",
        )
    db_task = Task.model_validate(task)
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    return db_task


@app.get("/tasks", response_model=List[Task])
def list_tasks(session: Session = Depends(get_session)) -> list[Task]:
    statement = select(Task).order_by(Task.deadline)
    return list(session.exec(statement).all())


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
