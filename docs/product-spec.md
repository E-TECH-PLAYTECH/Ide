# LifeOS Product Specification

## Purpose
LifeOS is a scheduling and planning service that stores events/tasks and returns diagnostics for timeline quality issues (overlaps and fragmentation). The MVP expands the current API in `lifeos/api.py` and data model in `lifeos/models.py` while preserving existing behavior for current clients.

## Scope

### In Scope (MVP)
1. Event management (create/list).
2. Task management (create/list).
3. Linting diagnostics from request payloads and persisted events.
4. Deterministic validation and error responses for malformed input.
5. Backward-compatible migration path for existing `events`, `tasks`, and `/lint` consumers.

### Out of Scope (MVP)
- Authn/authz.
- Multi-user tenancy.
- Calendar integrations.
- Automatic task scheduling into free slots.

---

## Domain Entities

### Event
Represents a scheduled block.

**Fields (current model in `lifeos/models.py`):**
- `id: str` (primary key)
- `content: str` (trimmed, non-empty)
- `tags: str`
- `start_time: datetime`
- `end_time: datetime` (must be `> start_time`)
- `is_fixed: bool` (default `False`)

### Task
Represents work to be done, optionally time-bound.

**Fields (current model in `lifeos/models.py`):**
- `id: str` (primary key)
- `content: str` (trimmed, non-empty)
- `tags: str`
- `status: str` (trimmed, non-empty)
- `deadline: datetime | null`
- `estimated_duration_minutes: int` (> 0)
- `dependency_ids: str` (serialized IDs in MVP for compatibility)

### Diagnostic
Represents a lint finding.

**Fields (current model in `lifeos/models.py`):**
- `severity: str` (`WARNING` or `ERROR` in existing linter usage)
- `message: str`
- `start: datetime`
- `end: datetime | null`
- `event_id: str | null`

---

## MVP Features

### Feature A: Create and list events
**Description**
- `POST /events` persists a unique event.
- `GET /events` returns events ordered by `start_time`.

**Workflow**
1. Client submits event payload.
2. API validates schema and time range.
3. API checks duplicate `id`.
4. API stores event and returns created object.

**Edge Cases**
- Duplicate ID -> `409` conflict.
- `content` empty/whitespace -> validation error.
- `end_time <= start_time` -> validation error.

**Acceptance Criteria**
- [ ] Creating a valid event returns `201` with persisted payload.
- [ ] Listing events returns deterministic order by `start_time`.
- [ ] Duplicate event IDs return `409` with stable error detail.
- [ ] Invalid time ranges are rejected with validation error payload.

### Feature B: Create and list tasks
**Description**
- `POST /tasks` persists a unique task.
- `GET /tasks` returns tasks ordered by `deadline`.

**Workflow**
1. Client submits task payload.
2. API validates schema (`status`, `estimated_duration_minutes`, etc.).
3. API checks duplicate `id`.
4. API stores task and returns created object.

**Edge Cases**
- Duplicate ID -> `409`.
- Empty `status` -> validation error.
- `estimated_duration_minutes <= 0` -> validation error.
- Null `deadline` remains allowed.

**Acceptance Criteria**
- [ ] Creating valid task returns `201` and record can be retrieved from `GET /tasks`.
- [ ] Duplicate task IDs return `409`.
- [ ] Invalid estimated duration is rejected with validation errors.
- [ ] Empty status is rejected with validation errors.

### Feature C: Lint schedule quality
**Description**
- `POST /lint` lints events supplied in request body.
- `GET /lint` loads persisted events and lints them.
- Existing linter rules in `lifeos/linter.py` produce:
  - `WARNING` for Swiss-cheese gaps between 15 and 45 minutes.
  - `ERROR` for overlapping events.

**Workflow**
1. API receives or loads events.
2. Events are sorted by `start_time`.
3. Fragmentation and overlap checks produce diagnostics.
4. Diagnostics are sorted by `start` and returned.

**Edge Cases**
- Empty event list -> empty diagnostics.
- Adjacent events (`end == next start`) -> no overlap diagnostic.
- Gaps < 15m or > 45m -> no fragmentation diagnostic.
- Nested overlaps generate diagnostic for each conflicting event encountered.

**Acceptance Criteria**
- [ ] Empty input returns `{ diagnostics: [] }`.
- [ ] 30-minute gap generates a `WARNING` diagnostic.
- [ ] Overlap generates an `ERROR` diagnostic with event reference.
- [ ] Response order is stable by timestamp.

---

## Phase 2 Features

### Feature D: Normalized task dependencies
**Description**
- Replace serialized `dependency_ids: str` with first-class relation support (e.g., `TaskDependency` table or JSON array field).

**Acceptance Criteria**
- [ ] API accepts and returns dependency IDs as array of task IDs.
- [ ] API rejects cycles with deterministic validation errors.
- [ ] Existing clients sending serialized string continue to work during migration window.

### Feature E: Schedule recommendations
**Description**
- Add endpoint to propose task placement in free windows while respecting fixed events and dependency order.

**Acceptance Criteria**
- [ ] Recommendations never overlap fixed events.
- [ ] Recommended order honors task dependencies.
- [ ] Unscheduled tasks include explicit reason codes.

### Feature F: Rich lint rule configuration
**Description**
- Make fragmentation thresholds configurable per request or org defaults.

**Acceptance Criteria**
- [ ] Client can set min/max gap thresholds.
- [ ] Defaults match MVP behavior when omitted.
- [ ] Invalid thresholds return typed validation errors.

---

## Backward Compatibility & Migration Notes

1. **Do not remove existing endpoints** in `lifeos/api.py` during MVP hardening.
2. **Keep current request/response field names** in `lifeos/models.py` unchanged for MVP.
3. **Preserve current linter semantics** in `lifeos/linter.py` (15-45 gap warning and overlap error) unless behind an opt-in flag.
4. Introduce additive changes first (new optional fields/endpoints) before any deprecation.
5. For future dependency normalization:
   - Accept both `dependency_ids` (string) and `dependency_ids_v2` (array) during a transition period.
   - Emit deprecation headers/messages when old format is used.
   - Provide one-time migration script for persisted tasks.
