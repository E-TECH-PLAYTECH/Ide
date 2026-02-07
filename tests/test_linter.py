from dataclasses import dataclass, field
from datetime import datetime
import unittest

from lifeos.linter import lint_events
from lifeos.models import DiagnosticSeverity


@dataclass
class EventPayload:
    id: str
    start_time: datetime
    end_time: datetime
    project_id: str | None = None
    tags: list[str] = field(default_factory=list)
    dependency_ids: list[str] = field(default_factory=list)
    deadline: datetime | None = None
    estimated_duration_minutes: int | None = None


def make_event(
    event_id: str,
    start_hour: int,
    start_minute: int,
    end_hour: int,
    end_minute: int,
    **kwargs: object,
) -> EventPayload:
    return EventPayload(
        id=event_id,
        start_time=datetime(2024, 1, 1, start_hour, start_minute),
        end_time=datetime(2024, 1, 1, end_hour, end_minute),
        **kwargs,
    )


class LintEventTests(unittest.TestCase):
    def test_overlap_code_is_deterministic(self) -> None:
        diagnostics, _ = lint_events(
            [
                make_event("A", 9, 0, 10, 0),
                make_event("B", 9, 30, 10, 30),
            ]
        )

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].code, "OVERLAP")
        self.assertEqual(diagnostics[0].event_id, "B")

    def test_dependency_violation_is_detected(self) -> None:
        diagnostics, _ = lint_events(
            [
                make_event("prep", 9, 0, 10, 0),
                make_event("execute", 9, 30, 10, 30, dependency_ids=["prep"]),
            ]
        )

        violation_codes = [diag.code for diag in diagnostics]
        self.assertIn("DEPENDENCY_VIOLATION", violation_codes)

    def test_deadline_risk_detects_insufficient_free_time(self) -> None:
        diagnostics, _ = lint_events(
            [
                make_event(
                    "important",
                    9,
                    0,
                    9,
                    30,
                    deadline=datetime(2024, 1, 1, 10, 0),
                    estimated_duration_minutes=90,
                ),
                make_event("busy", 9, 30, 9, 55),
            ]
        )

        self.assertIn("DEADLINE_RISK", [diag.code for diag in diagnostics])

    def test_context_switching_is_detected(self) -> None:
        diagnostics, _ = lint_events(
            [
                make_event("A", 9, 0, 9, 20, project_id="p1", tags=["one", "two"]),
                make_event("B", 9, 20, 9, 40, project_id="p2", tags=["three", "four"]),
                make_event("C", 9, 40, 10, 0, project_id="p3", tags=["five"]),
                make_event("D", 10, 0, 10, 20, project_id="p4", tags=["six"]),
            ]
        )

        self.assertIn("CONTEXT_SWITCHING", [diag.code for diag in diagnostics])

    def test_summary_contains_counts_and_top_issues(self) -> None:
        diagnostics, summary = lint_events(
            [
                make_event("A", 9, 0, 10, 0),
                make_event("B", 9, 30, 10, 30),
                make_event("C", 10, 45, 11, 0),
            ]
        )

        self.assertGreaterEqual(summary.severity_counts[DiagnosticSeverity.ERROR], 1)
        self.assertEqual(summary.top_blocking_issues[0].code, diagnostics[0].code)


if __name__ == "__main__":
    unittest.main()
