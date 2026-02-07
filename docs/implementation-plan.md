# LifeOS Full Implementation Plan (IDE-Based Productivity Manager)

## Objective
Deliver the full product and technical roadmap described in:
- `docs/product-spec.md`
- `docs/api-contract.md`
- `docs/scheduling-rules.md`
- `docs/operations.md`

This plan translates the design docs into an implementation sequence with code ownership, migration strategy, test requirements, and release checkpoints.

---

## 1) Delivery Strategy

### Phase 0 — Baseline Verification (stabilize current MVP behavior)
**Goal:** confirm existing MVP endpoints and linter behavior are fully locked before additive changes.

**Implementation tasks**
1. Validate endpoint behavior against API contract snapshots:
   - `GET /health/live`, `GET /health/ready`
   - `POST/GET /events`
   - `POST/GET /tasks`
   - `POST/GET /lint`
2. Freeze lint semantics to default thresholds (15/45) in tests.
3. Ensure deterministic ordering assertions across all listing endpoints.
4. Add regression tests for structured error envelope (`error.code`, `error.message`, `error.details`).

**Code areas**
- `lifeos/api.py`
- `lifeos/linter.py`
- `tests/integration/api/*`
- `tests/unit/*`

**Exit criteria**
- Green test suite proving MVP parity with design docs.

---

### Phase 1 — Dependency Normalization (Feature D)
**Goal:** move from serialized dependencies to first-class dependency representation with backward compatibility.

**Implementation tasks**
1. Data model changes:
   - Introduce/standardize normalized dependency storage via `TaskDependency` relations.
   - Keep `dependency_ids` legacy string readable/writable during migration window.
2. API contract extension:
   - Add additive field `dependency_ids_v2: list[str]` to task create/read/update payloads.
   - Dual-read logic:
     - Parse `dependency_ids_v2` when provided.
     - Fallback parse `dependency_ids` string for legacy clients.
   - Dual-write logic:
     - Persist normalized edges in `TaskDependency`.
     - Optionally mirror legacy string for compatibility.
3. Validation layer:
   - Reject unknown dependency IDs.
   - Detect cycles deterministically.
   - Return stable typed error payloads.
4. Migration support:
   - Add Alembic migration to backfill relation table from existing serialized values.
   - Add a one-time migration utility for operator-triggered re-sync.
5. Deprecation signaling:
   - Add response header or warning field when legacy `dependency_ids` input is used.

**Code areas**
- `lifeos/models.py`
- `lifeos/api.py`
- `lifeos/database.py`
- `alembic/versions/*`
- `tests/integration/api/test_tasks_api.py`
- `tests/integration/api/test_dependency_graph_api.py`

**Exit criteria**
- Tasks can be created/read with either legacy or v2 dependency input.
- Cycle + missing dependency validation covered by tests.

---

### Phase 2 — Scheduling Recommendations Engine (Feature E)
**Goal:** provide production-ready planning recommendations that respect fixed events and dependency order.

**Implementation tasks**
1. Planner input hardening:
   - Ensure planner request accepts explicit window bounds, fixed events, dependency graph, and capacity knobs.
2. Scheduling core improvements:
   - Preserve fixed events as immutable blocks.
   - Prioritize tasks by dependency-ready state and deadline.
   - Allocate time in earliest feasible slots.
   - Respect per-day capacity limits.
3. Reason-code standardization:
   - Replace free-text warning reasons with stable machine-readable codes.
   - Keep a human-readable message alongside code.
4. Deterministic behavior:
   - Explicit tie-break ordering (deadline, priority, id).
   - Deterministic output sorting for blocks and unmet warnings.
5. API endpoint finalization:
   - Validate and document planner endpoint request/response examples.
   - Add pagination/filter options if block counts can grow large.

**Code areas**
- `lifeos/planner.py`
- `lifeos/api.py`
- `lifeos/models.py`
- `docs/scheduling-rules.md` (sync with final reason codes)
- `tests/integration/api/test_plan_api.py`
- New planner-focused unit tests under `tests/unit/`

**Exit criteria**
- Planner never schedules overlapping fixed events.
- Dependency order is always respected.
- Unscheduled tasks include stable reason codes.

---

### Phase 3 — Configurable Lint Rules (Feature F)
**Goal:** add request-level lint threshold configuration while preserving default behavior.

**Implementation tasks**
1. Request schema extension:
   - Add optional `fragmentation_min_minutes` and `fragmentation_max_minutes` to lint request.
2. Validation:
   - Enforce non-negative bounds and `min <= max`.
3. Linter engine changes:
   - Parameterize fragmentation thresholds.
   - Keep defaults at 15/45 when omitted.
4. Observability:
   - Log effective thresholds used per lint run.
5. Compatibility guardrails:
   - Ensure current clients with old payload schema still pass unchanged.

**Code areas**
- `lifeos/linter.py`
- `lifeos/models.py`
- `lifeos/api.py`
- `tests/unit/test_linter_rules.py`
- `tests/unit/test_lint_contracts.py`

**Exit criteria**
- Threshold overrides work.
- Default lint behavior remains unchanged for existing payloads.

---

### Phase 4 — Operations & Hardening
**Goal:** production readiness and operational confidence.

**Implementation tasks**
1. Request tracing and metrics maturation:
   - Keep `X-Request-ID` propagation.
   - Add lightweight metrics endpoint or exporter integration (Prometheus-compatible optional).
2. Startup/deploy safeguards:
   - Ensure migrations are required pre-start (no implicit schema mutation).
   - Improve readiness probe detail for DB failures.
3. Data integrity and performance:
   - Add DB indexes for common filters/sorts (`events.start_time`, `tasks.deadline`, dependency edges).
   - Add constraints to prevent duplicate dependency edges.
4. Documentation and runbooks:
   - Update operations procedures and migration playbooks.

**Code areas**
- `lifeos/metrics.py`
- `lifeos/api.py`
- `lifeos/database.py`
- `alembic/versions/*`
- `docs/operations.md`

**Exit criteria**
- Repeatable deployment with migration-first workflow.
- Clear operational dashboards/logs for API and planner health.

---

## 2) Cross-Cutting Engineering Requirements

### A. Backward Compatibility Rules
1. Never remove or rename existing MVP endpoints during rollout.
2. Keep existing field names valid; add v2 fields additively.
3. Use deprecation notices before removing legacy formats.

### B. Validation & Error Consistency
1. All client-visible failures should use deterministic error codes.
2. Preserve structured error shape across endpoints.
3. Add test coverage for every explicit contract error path.

### C. Determinism & Time Semantics
1. Sort all list outputs with explicit tie-breakers.
2. Normalize timezone handling (UTC storage + explicit parsing rules).
3. Freeze current lint diagnostic ordering and message format unless versioned.

### D. Test Matrix
1. Unit tests: model validators, lint rules, planner ordering and capacity rules.
2. Integration tests: all endpoint happy-path + conflict + validation cases.
3. Migration tests: upgrade path from legacy dependency string data.
4. Contract tests: request/response snapshots for compatibility-sensitive endpoints.

---

## 3) Proposed Execution Order (Sprint-Oriented)

### Sprint 1
- MVP lock tests + deterministic error and ordering hardening.
- Dependency model groundwork in schema and API (dual-read).

### Sprint 2
- Dependency cycle/unknown validation.
- Migration/backfill script + dual-write.
- Complete dependency integration tests.

### Sprint 3
- Planner hardening and reason-code formalization.
- Expanded planner unit + integration coverage.

### Sprint 4
- Configurable lint thresholds.
- Contract updates and compatibility tests.

### Sprint 5
- Ops hardening (indexes, readiness detail, metrics exposure).
- Final documentation pass and release checklist signoff.

---

## 4) Definition of Done (Full Implementation)
A release is considered fully implemented when all conditions below are true:
1. MVP endpoint behavior remains compatible with existing clients.
2. Normalized dependencies are fully supported with migration path complete.
3. Planner recommendations are deterministic and enforce fixed-time + dependency rules.
4. Lint thresholds are configurable with default behavior preserved.
5. Operations runbook matches deployed behavior (health checks, logging, migrations, metrics).
6. Test suite covers all acceptance criteria from product and API docs.

---

## 5) Immediate Next Actions
1. Create issue backlog from this document (one ticket per implementation task cluster).
2. Start with Sprint 1 test hardening to establish a compatibility safety net.
3. Implement dependency normalization behind additive schema updates.
4. Ship in small, reversible increments with migration-first deploy sequencing.
