# LifeOS API Contract

This document describes the HTTP contract implemented by `lifeos/api.py` and schema constraints defined in `lifeos/models.py`.

## Conventions
- Base URL: implementation-defined (e.g., `http://localhost:8000`).
- Content type: `application/json`.
- Datetime format: ISO 8601 string.
- Validation errors follow FastAPI/Pydantic default shape (`422 Unprocessable Entity`).

---

## Schemas

### EventCreate / Event
```json
{
  "id": "evt_123",
  "content": "Focus block",
  "tags": "deep-work,planning",
  "start_time": "2026-01-12T09:00:00Z",
  "end_time": "2026-01-12T10:00:00Z",
  "is_fixed": false
}
```

**Validation rules**
- `content`: non-empty after trim.
- `end_time > start_time`.
- `id`: unique among events (enforced by API conflict check).

### TaskCreate / Task
```json
{
  "id": "task_123",
  "content": "Write quarterly plan",
  "tags": "planning,strategy",
  "status": "todo",
  "deadline": "2026-01-20T17:00:00Z",
  "estimated_duration_minutes": 90,
  "dependency_ids": "task_120,task_121"
}
```

**Validation rules**
- `content`: non-empty after trim.
- `status`: non-empty after trim.
- `estimated_duration_minutes > 0`.
- `id`: unique among tasks.
- `deadline`: nullable.

### LintRequest
```json
{
  "events": [
    {
      "id": "evt_1",
      "start_time": "2026-01-12T09:00:00Z",
      "end_time": "2026-01-12T10:00:00Z"
    }
  ]
}
```

### LintResponse
```json
{
  "diagnostics": [
    {
      "severity": "WARNING",
      "message": "Swiss Cheese Gap: 30m",
      "start": "2026-01-12T10:00:00Z",
      "end": "2026-01-12T10:30:00Z",
      "event_id": "evt_1"
    }
  ]
}
```

---

## Endpoints

## `GET /health`
Health probe.

**Response**
- `200 OK`
```json
{ "status": "ok" }
```

**Acceptance Criteria**
- [ ] Always returns `200` with `{ "status": "ok" }` when process is healthy.

---

## `POST /events`
Create event.

**Request Body**
- `EventCreate`.

**Responses**
- `201 Created`: returns `Event`.
- `409 Conflict`: duplicate event `id`.
- `422 Unprocessable Entity`: schema/validation failure.

**409 Example**
```json
{ "detail": "Event with this id already exists" }
```

**422 Validation Error Shape (example)**
```json
{
  "detail": [
    {
      "loc": ["body", "end_time"],
      "msg": "Value error, end_time must be after start_time",
      "type": "value_error"
    }
  ]
}
```

**Acceptance Criteria**
- [ ] Valid request returns `201` and echoes persisted values.
- [ ] Duplicate `id` returns `409` and stable conflict detail.
- [ ] Empty content or invalid time range returns `422`.

---

## `GET /events`
List events.

**Responses**
- `200 OK`: array of `Event` sorted by `start_time` ascending.

**Acceptance Criteria**
- [ ] Returns JSON array.
- [ ] Ordering is deterministic by `start_time`.

---

## `POST /tasks`
Create task.

**Request Body**
- `TaskCreate`.

**Responses**
- `201 Created`: returns `Task`.
- `409 Conflict`: duplicate task `id`.
- `422 Unprocessable Entity`: schema/validation failure.

**409 Example**
```json
{ "detail": "Task with this id already exists" }
```

**422 Validation Error Cases**
- Empty/whitespace `status`.
- `estimated_duration_minutes <= 0`.
- Empty/whitespace `content`.

**Acceptance Criteria**
- [ ] Valid request returns `201`.
- [ ] Duplicate `id` returns `409`.
- [ ] Invalid status/duration returns `422` with field-level errors.

---

## `GET /tasks`
List tasks.

**Responses**
- `200 OK`: array of `Task` sorted by `deadline` ascending (`null` ordering is DB-defined; must be documented in implementation notes/tests).

**Acceptance Criteria**
- [ ] Returns JSON array.
- [ ] Ordering follows backend `ORDER BY deadline` behavior.

---

## `POST /lint`
Lint events from request payload.

**Request Body**
- `LintRequest`.

**Responses**
- `200 OK`: `LintResponse`.
- `422 Unprocessable Entity`: malformed request.

**Rules currently applied (`lifeos/linter.py`)**
- Fragmentation warning when 15 <= gap_minutes <= 45.
- Overlap error when next event starts before currently active end.

**Acceptance Criteria**
- [ ] Empty events list returns empty diagnostics.
- [ ] Gap within threshold produces warning.
- [ ] Overlap produces error.

---

## `GET /lint`
Lint persisted events.

**Responses**
- `200 OK`: `LintResponse` based on all persisted events.

**Acceptance Criteria**
- [ ] Uses same linter semantics as `POST /lint`.
- [ ] Returns deterministic diagnostic ordering by start timestamp.

---

## Backward Compatibility & Migration Notes

1. Existing clients using all six endpoints must continue to function unchanged.
2. Do not rename existing payload fields in current API versions.
3. If introducing v2 payloads in future:
   - Keep old fields optional for at least one deprecation cycle.
   - Document deprecation timeline and response headers.
4. Ensure lint outputs keep existing `severity` and `message` conventions unless versioned.
5. For dependency model migration, support dual-write/dual-read (string + array) before fully switching storage format.
