from __future__ import annotations

from typing import Iterator

from sqlalchemy import text
from sqlmodel import Session, create_engine

from .settings import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, echo=False)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def database_is_reachable() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
