from __future__ import annotations

from typing import Iterator

from sqlmodel import Session, create_engine

from .settings import get_database_url

engine = create_engine(get_database_url(), echo=False)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
