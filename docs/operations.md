# Operations Runbook

## Runtime configuration

LifeOS loads runtime settings from environment variables through a centralized settings object (`lifeos.settings.Settings`).

| Variable | Default | Notes |
|---|---|---|
| `LIFEOS_ENV` | `dev` | Allowed: `dev`, `test`, `prod`. |
| `LIFEOS_DATABASE_URL` | env-dependent | Required in `prod`; optional in `dev`/`test`. |
| `LIFEOS_HOST` | `0.0.0.0` | Bind host for app startup (`python -m lifeos.main`). |
| `LIFEOS_PORT` | `8000` | Bind port for app startup. |
| `LIFEOS_LOG_LEVEL` | `INFO` | Python logging level. |
| `LIFEOS_LOG_FORMAT` | `json` | Structured logging mode (JSON payloads). |

## Health endpoints

- **Liveness**: `GET /health/live`
  - Indicates the process is alive.
  - Returns `200` with `{ "status": "ok" }`.
- **Readiness**: `GET /health/ready`
  - Indicates dependency readiness.
  - Performs a DB reachability probe (`SELECT 1`).
  - Returns `200` with `{ "status": "ready" }` when DB is reachable.
  - Returns `503` with `{ "status": "not_ready" }` when DB probe fails.

## Request tracing and logging

- Every request is assigned a request ID.
  - Incoming `X-Request-ID` is reused when present.
  - Otherwise a UUID is generated.
  - The response always includes `X-Request-ID`.
- Request lifecycle logs are emitted:
  - `request.started`
  - `request.completed`
- Lint execution logs are emitted:
  - `lint.executed` with source (`request` or `database`), event count, diagnostic count, and duration.

## Metrics hooks

The service tracks in-memory operational hooks for:

- Total request count.
- Request count by status code.
- Request latency samples (milliseconds).
- Lint execution duration samples (milliseconds).

These hooks are currently in-process only (no exporter endpoint yet).

## Deployment expectations

1. Run migrations before app startup in all environments.
2. For production, always set a durable `LIFEOS_DATABASE_URL`.
3. Configure platform health checks:
   - Liveness probe: `/health/live`
   - Readiness probe: `/health/ready`
4. Ensure logs are collected from stdout/stderr; logs are structured JSON records.
5. Propagate an external request ID header from ingress where possible for distributed tracing continuity.
