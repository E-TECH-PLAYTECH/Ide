from __future__ import annotations

from datetime import datetime

from .models import Diagnostic, Event


def check_fragmentation(events: list[Event]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    sorted_events = sorted(events, key=lambda event: event.start_time)

    for current_event, next_event in zip(sorted_events, sorted_events[1:]):
        gap = (next_event.start_time - current_event.end_time).total_seconds() / 60

        if 15 <= gap <= 45:
            diagnostics.append(
                Diagnostic(
                    severity="WARNING",
                    message=f"Swiss Cheese Gap: {int(gap)}m",
                    start=current_event.end_time,
                    end=next_event.start_time,
                    event_id=current_event.id,
                )
            )

    return diagnostics


def check_overlaps(events: list[Event]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    sorted_events = sorted(events, key=lambda event: event.start_time)

    for current_event, next_event in zip(sorted_events, sorted_events[1:]):
        if next_event.start_time < current_event.end_time:
            diagnostics.append(
                Diagnostic(
                    severity="ERROR",
                    message="Schedule overlap detected",
                    start=next_event.start_time,
                    end=min(next_event.end_time, current_event.end_time),
                    event_id=next_event.id,
                )
            )

    return diagnostics


def lint_events(events: list[Event]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(check_fragmentation(events))
    diagnostics.extend(check_overlaps(events))
    diagnostics.sort(key=lambda item: item.start)
    return diagnostics


def now_utc() -> datetime:
    return datetime.utcnow()
