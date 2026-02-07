from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from .models import (
    PlanBlock,
    PlanEventInput,
    PlannerRequest,
    PlannerResponse,
    PlannerTaskInput,
    UnmetTaskWarning,
)


@dataclass(frozen=True)
class _Interval:
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


def _daterange(start_day: date, end_day: date) -> list[date]:
    days: list[date] = []
    current = start_day
    while current <= end_day:
        days.append(current)
        current = current + timedelta(days=1)
    return days


def _clamp_interval(interval: _Interval, window_start: datetime, window_end: datetime) -> _Interval | None:
    start = max(interval.start, window_start)
    end = min(interval.end, window_end)
    if end <= start:
        return None
    return _Interval(start=start, end=end)


def _subtract_interval(base: list[_Interval], blocked: _Interval) -> list[_Interval]:
    result: list[_Interval] = []
    for interval in base:
        if blocked.end <= interval.start or blocked.start >= interval.end:
            result.append(interval)
            continue

        if blocked.start > interval.start:
            result.append(_Interval(start=interval.start, end=blocked.start))
        if blocked.end < interval.end:
            result.append(_Interval(start=blocked.end, end=interval.end))
    return result


def _build_daily_slots(request: PlannerRequest) -> dict[date, list[_Interval]]:
    slots: dict[date, list[_Interval]] = {}
    for day in _daterange(request.window_start.date(), request.window_end.date()):
        start = datetime.combine(day, time(hour=request.focus_hours_start))
        end = datetime.combine(day, time(hour=request.focus_hours_end))
        clamped = _clamp_interval(
            _Interval(start=start, end=end),
            request.window_start,
            request.window_end,
        )
        slots[day] = [clamped] if clamped else []

    fixed_events = sorted(
        request.fixed_events,
        key=lambda event: (event.start_time, event.end_time, event.id),
    )
    for event in fixed_events:
        blocked = _clamp_interval(
            _Interval(start=event.start_time, end=event.end_time),
            request.window_start,
            request.window_end,
        )
        if not blocked:
            continue
        day = blocked.start.date()
        if day in slots:
            slots[day] = _subtract_interval(slots[day], blocked)
    return slots


def _normalize_dependencies(
    tasks: list[PlannerTaskInput], dependency_graph: dict[str, list[str]]
) -> dict[str, set[str]]:
    task_ids = {task.id for task in tasks}
    dependencies: dict[str, set[str]] = {task.id: set(task.dependency_ids) for task in tasks}
    for task_id, predecessor_ids in dependency_graph.items():
        if task_id not in task_ids:
            continue
        dependencies[task_id].update(predecessor_ids)
    return dependencies


def _create_fixed_blocks(fixed_events: list[PlanEventInput]) -> list[PlanBlock]:
    blocks: list[PlanBlock] = []
    for event in sorted(fixed_events, key=lambda value: (value.start_time, value.end_time, value.id)):
        blocks.append(
            PlanBlock(
                block_type="fixed_event",
                ref_id=event.id,
                start_time=event.start_time,
                end_time=event.end_time,
                rationale="Fixed event blocks planning capacity during this time.",
            )
        )
    return blocks


def build_plan(request: PlannerRequest) -> PlannerResponse:
    dependencies = _normalize_dependencies(request.tasks, request.dependency_graph)

    slots_by_day = _build_daily_slots(request)
    day_capacity_remaining: dict[date, int] = {}
    for day, slots in slots_by_day.items():
        available_minutes = sum(slot.minutes for slot in slots)
        day_capacity_remaining[day] = min(request.max_planned_minutes_per_day, available_minutes)

    task_remaining = {task.id: task.estimated_duration_minutes for task in request.tasks}
    completed: set[str] = set()
    planned_blocks: list[PlanBlock] = _create_fixed_blocks(request.fixed_events)
    warnings: list[UnmetTaskWarning] = []

    while True:
        ready_tasks = [
            task
            for task in request.tasks
            if task_remaining[task.id] > 0 and dependencies.get(task.id, set()).issubset(completed)
        ]
        ready_tasks.sort(key=lambda task: (task.deadline or datetime.max, task.id))
        if not ready_tasks:
            break

        any_progress = False
        for task in ready_tasks:
            remaining = task_remaining[task.id]
            for day in sorted(slots_by_day.keys()):
                if remaining <= 0:
                    break
                if day_capacity_remaining[day] <= 0:
                    continue

                updated_slots: list[_Interval] = []
                for slot in slots_by_day[day]:
                    if remaining <= 0 or day_capacity_remaining[day] <= 0:
                        updated_slots.append(slot)
                        continue

                    candidate_end = slot.end
                    if task.deadline:
                        candidate_end = min(candidate_end, task.deadline)
                    if candidate_end <= slot.start:
                        updated_slots.append(slot)
                        continue

                    usable_minutes = int((candidate_end - slot.start).total_seconds() // 60)
                    allocatable = min(usable_minutes, remaining, day_capacity_remaining[day])
                    if allocatable <= 0:
                        updated_slots.append(slot)
                        continue

                    block_end = slot.start + timedelta(minutes=allocatable)
                    planned_blocks.append(
                        PlanBlock(
                            block_type="task",
                            ref_id=task.id,
                            start_time=slot.start,
                            end_time=block_end,
                            rationale=(
                                f"Scheduled in earliest available focus slot; {remaining - allocatable} minutes remain afterward."
                            ),
                        )
                    )
                    any_progress = True
                    remaining -= allocatable
                    day_capacity_remaining[day] -= allocatable

                    if block_end < slot.end:
                        updated_slots.append(_Interval(start=block_end, end=slot.end))

                slots_by_day[day] = updated_slots

            task_remaining[task.id] = remaining
            if remaining == 0:
                completed.add(task.id)

        if not any_progress:
            break

    for task in sorted(request.tasks, key=lambda item: item.id):
        remaining = task_remaining[task.id]
        if remaining == 0:
            continue

        missing_dependencies = sorted(dependencies.get(task.id, set()) - completed)
        if missing_dependencies:
            reason = f"Blocked by unmet dependencies: {', '.join(missing_dependencies)}"
        elif task.deadline and task.deadline < request.window_end:
            reason = "Insufficient capacity before strict deadline."
        else:
            reason = "Insufficient capacity within planning window."

        warnings.append(
            UnmetTaskWarning(
                task_id=task.id,
                minutes_unplanned=remaining,
                reason=reason,
            )
        )

    ordered_blocks = sorted(
        planned_blocks,
        key=lambda block: (block.start_time, block.end_time, block.block_type, block.ref_id),
    )

    return PlannerResponse(blocks=ordered_blocks, unmet_task_warnings=warnings)
