from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol

from .models import Diagnostic, DiagnosticSeverity, LintSummary


class LintEventLike(Protocol):
    id: str
    start_time: datetime
    end_time: datetime
    project_id: str | None
    tags: list[str]
    dependency_ids: list[str]
    deadline: datetime | None
    estimated_duration_minutes: int | None


def check_fragmentation(events: list[LintEventLike]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    sorted_events = sorted(events, key=lambda event: event.start_time)

    for current_event, next_event in zip(sorted_events, sorted_events[1:]):
        gap = (next_event.start_time - current_event.end_time).total_seconds() / 60

        if 15 <= gap <= 45:
            diagnostics.append(
                Diagnostic(
                    code="FRAGMENTATION",
                    severity=DiagnosticSeverity.WARNING,
                    message=f"Swiss Cheese Gap: {int(gap)}m",
                    start=current_event.end_time,
                    end=next_event.start_time,
                    event_id=current_event.id,
                    hint=(
                        "Merge adjacent work by moving one block to close the gap "
                        f"between {current_event.end_time.isoformat()} and {next_event.start_time.isoformat()}."
                    ),
                )
            )

    return diagnostics


def check_overlaps(events: list[LintEventLike]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    sorted_events = sorted(events, key=lambda event: event.start_time)

    if not sorted_events:
        return diagnostics

    active_end = sorted_events[0].end_time

    for next_event in sorted_events[1:]:
        if next_event.start_time < active_end:
            diagnostics.append(
                Diagnostic(
                    code="OVERLAP",
                    severity=DiagnosticSeverity.ERROR,
                    message="Schedule overlap detected",
                    start=next_event.start_time,
                    end=min(next_event.end_time, active_end),
                    event_id=next_event.id,
                    hint="Move one of the overlapping events so time ranges no longer intersect.",
                )
            )

        if next_event.end_time > active_end:
            active_end = next_event.end_time

    diagnostics.sort(key=lambda item: (item.start, item.end or item.start, item.event_id or ""))

    return diagnostics


def check_dependency_violations(events: list[LintEventLike]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    events_by_id = {event.id: event for event in events}

    for event in sorted(events, key=lambda item: item.start_time):
        for dependency_id in sorted(set(event.dependency_ids)):
            dependency = events_by_id.get(dependency_id)
            if dependency is None:
                continue
            if event.start_time < dependency.end_time:
                diagnostics.append(
                    Diagnostic(
                        code="DEPENDENCY_VIOLATION",
                        severity=DiagnosticSeverity.ERROR,
                        message=f"Task scheduled before prerequisite '{dependency_id}' completes",
                        start=event.start_time,
                        end=dependency.end_time,
                        event_id=event.id,
                        hint=(
                            f"Move '{event.id}' to start after {dependency.end_time.isoformat()} "
                            f"or reschedule prerequisite '{dependency_id}'."
                        ),
                    )
                )

    return diagnostics


def check_deadline_risk(events: list[LintEventLike]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    sorted_events = sorted(events, key=lambda item: item.start_time)

    for event in sorted_events:
        if event.deadline is None or event.estimated_duration_minutes is None:
            continue
        if event.end_time >= event.deadline:
            diagnostics.append(
                Diagnostic(
                    code="DEADLINE_RISK",
                    severity=DiagnosticSeverity.ERROR,
                    message="Task is scheduled past its deadline",
                    start=event.start_time,
                    end=event.end_time,
                    event_id=event.id,
                    hint=f"Move this task to finish before {event.deadline.isoformat()}.",
                )
            )
            continue

        free_minutes = 0.0
        pointer = event.end_time
        for next_event in sorted_events:
            if next_event.start_time >= event.deadline or next_event.id == event.id:
                continue
            if next_event.end_time <= pointer:
                continue

            gap_end = min(next_event.start_time, event.deadline)
            if gap_end > pointer:
                free_minutes += (gap_end - pointer).total_seconds() / 60

            pointer = max(pointer, next_event.end_time)
            if pointer >= event.deadline:
                break

        if pointer < event.deadline:
            free_minutes += (event.deadline - pointer).total_seconds() / 60

        remaining_needed = max(0, event.estimated_duration_minutes - int((event.end_time - event.start_time).total_seconds() / 60))
        if remaining_needed > 0 and free_minutes < remaining_needed:
            earliest_start = event.deadline - timedelta(minutes=event.estimated_duration_minutes)
            diagnostics.append(
                Diagnostic(
                    code="DEADLINE_RISK",
                    severity=DiagnosticSeverity.WARNING,
                    message="Insufficient free time before deadline",
                    start=event.end_time,
                    end=event.deadline,
                    event_id=event.id,
                    hint=(
                        f"Reserve at least {remaining_needed} more minutes before deadline. "
                        f"Suggested move window: {earliest_start.isoformat()} to {event.deadline.isoformat()}."
                    ),
                )
            )

    return diagnostics


def check_context_switching(events: list[LintEventLike], window_size: int = 4) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    sorted_events = sorted(events, key=lambda item: item.start_time)

    if len(sorted_events) < window_size:
        return diagnostics

    for idx in range(len(sorted_events) - window_size + 1):
        window = sorted_events[idx : idx + window_size]
        unique_projects = len({event.project_id for event in window if event.project_id is not None})
        unique_tags = len({tag for event in window for tag in event.tags})
        if unique_projects >= 3 or unique_tags >= 6:
            diagnostics.append(
                Diagnostic(
                    code="CONTEXT_SWITCHING",
                    severity=DiagnosticSeverity.WARNING,
                    message="Excessive context switching across projects/tags",
                    start=window[0].start_time,
                    end=window[-1].end_time,
                    event_id=window[0].id,
                    hint="Batch related tasks together to reduce project and tag switching in this interval.",
                )
            )

    return diagnostics


def summarize_diagnostics(diagnostics: list[Diagnostic]) -> LintSummary:
    severity_counts: dict[DiagnosticSeverity, int] = {
        DiagnosticSeverity.INFO: 0,
        DiagnosticSeverity.WARNING: 0,
        DiagnosticSeverity.ERROR: 0,
    }
    for diagnostic in diagnostics:
        severity_counts[diagnostic.severity] = severity_counts.get(diagnostic.severity, 0) + 1

    ranked = sorted(
        diagnostics,
        key=lambda item: (
            0 if item.severity == DiagnosticSeverity.ERROR else 1 if item.severity == DiagnosticSeverity.WARNING else 2,
            item.start,
            item.code,
            item.event_id or "",
        ),
    )

    return LintSummary(severity_counts=severity_counts, top_blocking_issues=ranked[:3])


def lint_events(events: list[LintEventLike]) -> tuple[list[Diagnostic], LintSummary]:
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(check_fragmentation(events))
    diagnostics.extend(check_overlaps(events))
    diagnostics.extend(check_deadline_risk(events))
    diagnostics.extend(check_dependency_violations(events))
    diagnostics.extend(check_context_switching(events))
    diagnostics.sort(key=lambda item: (item.start, item.code, item.event_id or ""))
    return diagnostics, summarize_diagnostics(diagnostics)


def now_utc() -> datetime:
    return datetime.utcnow()
