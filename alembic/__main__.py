from __future__ import annotations

import argparse
import importlib.util
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from sqlmodel import SQLModel

from lifeos import models  # noqa: F401
from lifeos.settings import get_database_url

VERSIONS_DIR = Path(__file__).parent / "versions"
MIGRATION_TABLE = "_lifeos_migrations"


def _load_migrations() -> list[tuple[str, object]]:
    migrations: list[tuple[str, object]] = []
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        revision = getattr(module, "revision", path.stem)
        migrations.append((revision, module))
    return migrations


def _ensure_migration_table(connection) -> None:
    connection.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {MIGRATION_TABLE} (
                revision VARCHAR PRIMARY KEY
            )
            """
        )
    )


def cmd_upgrade(_: argparse.Namespace) -> int:
    engine = create_engine(get_database_url())
    migrations = _load_migrations()
    with engine.begin() as connection:
        _ensure_migration_table(connection)
        applied = {
            row[0]
            for row in connection.execute(text(f"SELECT revision FROM {MIGRATION_TABLE}"))
        }
        for revision, module in migrations:
            if revision in applied:
                continue
            module.upgrade(connection)
            connection.execute(
                text(f"INSERT INTO {MIGRATION_TABLE} (revision) VALUES (:revision)"),
                {"revision": revision},
            )
    return 0


def _schema_signature(engine_url: str) -> dict[str, set[str]]:
    engine = create_engine(engine_url)
    inspector = inspect(engine)
    signature: dict[str, set[str]] = {}
    for table_name in inspector.get_table_names():
        signature[table_name] = {col["name"] for col in inspector.get_columns(table_name)}
    return signature


def cmd_check(_: argparse.Namespace) -> int:
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        tmp_url = f"sqlite:///{tmp.name}"
        engine = create_engine(tmp_url)
        SQLModel.metadata.create_all(engine)
        expected = _schema_signature(tmp_url)

        apply_engine = create_engine(tmp_url)
        with apply_engine.begin() as connection:
            _ensure_migration_table(connection)
            for _, module in _load_migrations():
                module.upgrade(connection)
        actual = _schema_signature(tmp_url)

    expected.pop(MIGRATION_TABLE, None)
    actual.pop(MIGRATION_TABLE, None)
    if expected != actual:
        raise SystemExit("Migration check failed: migration schema differs from SQLModel metadata")
    print("Migration check passed")
    return 0


def cmd_revision(args: argparse.Namespace) -> int:
    raise SystemExit(
        "Autogeneration is not available in this lightweight runner. "
        "Create a new file under alembic/versions manually."
    )


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m alembic")
    subparsers = parser.add_subparsers(dest="command", required=True)

    up_parser = subparsers.add_parser("upgrade")
    up_parser.add_argument("target")
    up_parser.set_defaults(func=cmd_upgrade)

    check_parser = subparsers.add_parser("check")
    check_parser.set_defaults(func=cmd_check)

    rev_parser = subparsers.add_parser("revision")
    rev_parser.add_argument("--autogenerate", action="store_true")
    rev_parser.add_argument("-m", "--message", required=False)
    rev_parser.set_defaults(func=cmd_revision)

    args = parser.parse_args()
    if args.command == "upgrade" and args.target != "head":
        raise SystemExit("Only 'upgrade head' is supported")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
