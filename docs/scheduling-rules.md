# LifeOS Scheduling Rules

This document formalizes scheduling logic currently implemented in `lifeos/linter.py`, plus forward-compatible rules for fixed-time constraints and task dependencies.

## 1) Conflict Resolution

## Current MVP Rule
- A conflict exists when an event starts before the active event window ends.
- For sorted events, if `next.start_time < active_end`, emit overlap diagnostic.
- Diagnostic severity: `ERROR`.
- Diagnostic range: `[next.start_time, min(next.end_time, active_end)]`.

## Tie/Boundary Behavior
- If `next.start_time == active_end`, this is **not** a conflict.
- Events are evaluated in ascending `start_time`.

## Resolution Policy (MVP)
- Linter is observational only; it reports conflicts and does not mutate schedule.

## Acceptance Criteria
- [ ] Two overlapping events produce at least one `ERROR` diagnostic.
- [ ] Adjacent events (touching boundaries) produce no overlap diagnostic.
- [ ] Output is stable for same event set and ordering.

---

## 2) Fragmentation Thresholds

## Current MVP Rule
- Compute gap in minutes between consecutive sorted events:
  - `gap = next.start_time - current.end_time`.
- Emit warning if `15 <= gap <= 45`.
- Severity: `WARNING`.
- Message format: `Swiss Cheese Gap: <Xm>`.

## Non-triggering Cases
- Gaps < 15 minutes.
- Gaps > 45 minutes.
- Negative gaps (already handled by overlap rule).

## Phase 2 Extension
- Allow configurable thresholds per lint request (e.g., `fragmentation_min`, `fragmentation_max`).
- Default remains 15/45 for backward compatibility.

## Acceptance Criteria
- [ ] A 20-minute gap yields one `WARNING`.
- [ ] A 10-minute or 60-minute gap yields no fragmentation warning.
- [ ] Configurable thresholds (Phase 2) do not alter default behavior when omitted.

---

## 3) Fixed-Time Constraints

## Current MVP State
- `Event.is_fixed` exists in model but is not used by linter conflict checks.

## Required Rule (Phase 2 Scheduling Engine)
- Fixed events are immutable anchors.
- Auto-scheduled or flexible items must not overlap fixed events.
- If placement is impossible without breaking fixed constraints, mark item unscheduled with reason code.

## Conflict Priority
1. Never move fixed events automatically.
2. Attempt to move flexible candidate windows.
3. If unresolved, return explicit conflict diagnostics.

## Acceptance Criteria
- [ ] Scheduler never proposes a slot overlapping a fixed event.
- [ ] Fixed events are not altered by automated resolution.
- [ ] Unresolvable requests include machine-readable reason.

---

## 4) Dependency Handling

## Current MVP State
- Task dependencies are stored as serialized string `dependency_ids`.
- Linter does not currently evaluate dependency consistency.

## Required Rules (Phase 2)
1. A task may only be scheduled after all dependencies are complete/scheduled earlier.
2. Cyclic dependency graphs are invalid.
3. Missing dependency references are validation errors.
4. Dependency violations should return deterministic error codes/messages.

## Suggested Validation Order
1. Parse dependency input.
2. Verify all referenced IDs exist.
3. Build graph and detect cycles.
4. Topologically sort for scheduling order.

## Acceptance Criteria
- [ ] Scheduling output always respects topological dependency order.
- [ ] Cyclic dependencies fail with explicit validation error.
- [ ] Missing dependency IDs fail with explicit validation error.

---

## Backward Compatibility & Migration Notes

1. Preserve MVP lint behavior exactly until versioned scheduling APIs are introduced.
2. Continue accepting current `Event` and `Task` payloads from `lifeos/models.py`.
3. For dependency modernization:
   - Introduce `dependency_ids_v2: string[]` as additive field.
   - Read both formats in API layer (`lifeos/api.py`) during migration.
   - Normalize internally to array representation before rule evaluation.
4. Keep existing linter endpoint contracts stable (`/lint` GET/POST), and add new scheduling endpoints instead of changing current response schema.
