from __future__ import annotations

import os
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

DEFAULT_DB_URL = "sqlite:///lifeos.db"


def database_url() -> str:
    return os.environ.get("LIFEOS_DATABASE_URL", DEFAULT_DB_URL)


engine = create_engine(database_url(), echo=False)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
