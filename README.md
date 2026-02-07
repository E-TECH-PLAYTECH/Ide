# LifeOS

## Planning documentation

- Full implementation roadmap: `docs/implementation-plan.md`

## Environment profiles

LifeOS supports three runtime profiles through `LIFEOS_ENV`:

- `dev` (default): uses `sqlite:///lifeos-dev.db` unless `LIFEOS_DATABASE_URL` is set.
- `test`: uses `sqlite:///lifeos-test.db` unless `LIFEOS_DATABASE_URL` is set.
- `prod`: requires `LIFEOS_DATABASE_URL` to be explicitly set.

`LIFEOS_DATABASE_URL` always takes precedence when provided.

## Database migrations (Alembic)

Schema changes are managed by the repository's Alembic-equivalent migration runner against SQLModel metadata. The API no longer mutates schema on startup.

### Apply migrations

```bash
LIFEOS_ENV=dev python -m alembic upgrade head
```

### Create a new migration after model changes

Create a timestamped file in `alembic/versions/` and implement `upgrade(connection)` with the required DDL.

```bash
cp alembic/versions/20260101_000001_initial_schema.py alembic/versions/<timestamp>_<name>.py
```

### Validate migration state

```bash
LIFEOS_ENV=dev python -m alembic check
```

### Run the API

```bash
LIFEOS_ENV=dev python -m uvicorn lifeos.api:app --reload
```

> In production, run `python -m alembic upgrade head` during deploy before starting the API process.
