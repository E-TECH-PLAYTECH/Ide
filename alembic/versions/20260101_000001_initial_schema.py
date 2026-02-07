"""Initial SQLModel schema."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

revision = "20260101_000001"
down_revision = None


def upgrade(connection: Connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS project (
                name VARCHAR NOT NULL,
                description VARCHAR,
                id VARCHAR NOT NULL PRIMARY KEY,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS event (
                content VARCHAR NOT NULL,
                tags JSON,
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                is_fixed BOOLEAN NOT NULL,
                project_id VARCHAR,
                id VARCHAR NOT NULL PRIMARY KEY,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(project_id) REFERENCES project (id)
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS task (
                content VARCHAR NOT NULL,
                tags JSON,
                status VARCHAR NOT NULL,
                deadline DATETIME,
                estimated_duration_minutes INTEGER NOT NULL,
                project_id VARCHAR,
                id VARCHAR NOT NULL PRIMARY KEY,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                completed_at DATETIME,
                FOREIGN KEY(project_id) REFERENCES project (id)
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS routine (
                id VARCHAR NOT NULL PRIMARY KEY,
                name VARCHAR NOT NULL,
                task_template VARCHAR NOT NULL,
                project_id VARCHAR,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(project_id) REFERENCES project (id)
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS taskdependency (
                predecessor_task_id VARCHAR NOT NULL,
                successor_task_id VARCHAR NOT NULL,
                created_at DATETIME NOT NULL,
                PRIMARY KEY (predecessor_task_id, successor_task_id),
                FOREIGN KEY(predecessor_task_id) REFERENCES task (id),
                FOREIGN KEY(successor_task_id) REFERENCES task (id)
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS recurringrule (
                id VARCHAR NOT NULL PRIMARY KEY,
                routine_id VARCHAR NOT NULL,
                cadence VARCHAR NOT NULL,
                interval INTEGER NOT NULL,
                start_at DATETIME NOT NULL,
                end_at DATETIME,
                FOREIGN KEY(routine_id) REFERENCES routine (id)
            )
            """
        )
    )
