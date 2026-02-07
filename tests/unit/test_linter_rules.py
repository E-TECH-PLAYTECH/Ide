from __future__ import annotations

import unittest
from datetime import datetime

from lifeos.linter import lint_events
from lifeos.models import DiagnosticSeverity
from tests.support.fixtures import build_lint_event


class LintEventRuleTests(unittest.TestCase):
    def test_overlap_code_is_deterministic(self) -> None:
        diagnostics, _ = lint_events(
            [
                build_lint_event("A", 9, 0, 10, 0),
                build_lint_event("B", 9, 30, 10, 30),
            ]
        )

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].code, "OVERLAP")
        self.assertEqual(diagnostics[0].event_id, "B")

    def test_fragmentation_gap_is_detected(self) -> None:
        diagnostics, _ = lint_events(
            [
                build_lint_event("A", 9, 0, 9, 30),
                build_lint_event("B", 9, 50, 10, 30),
            ]
        )

        self.assertIn("FRAGMENTATION", [diag.code for diag in diagnostics])

    def test_dependency_violation_is_detected(self) -> None:
        diagnostics, _ = lint_events(
            [
                build_lint_event("prep", 9, 0, 10, 0),
                build_lint_event("execute", 9, 30, 10, 30, dependency_ids=["prep"]),
            ]
        )

        self.assertIn("DEPENDENCY_VIOLATION", [diag.code for diag in diagnostics])

    def test_deadline_risk_error_when_event_ends_after_deadline(self) -> None:
        diagnostics, _ = lint_events(
            [
                build_lint_event(
                    "late",
                    9,
                    0,
                    10,
                    30,
                    deadline=datetime(2024, 1, 1, 10, 0),
                    estimated_duration_minutes=90,
                )
            ]
        )

        deadline_diagnostics = [diag for diag in diagnostics if diag.code == "DEADLINE_RISK"]
        self.assertEqual(len(deadline_diagnostics), 1)
        self.assertEqual(deadline_diagnostics[0].severity, DiagnosticSeverity.ERROR)

    def test_deadline_risk_detects_insufficient_free_time(self) -> None:
        diagnostics, _ = lint_events(
            [
                build_lint_event(
                    "important",
                    9,
                    0,
                    9,
                    30,
                    deadline=datetime(2024, 1, 1, 10, 0),
                    estimated_duration_minutes=90,
                ),
                build_lint_event("busy", 9, 30, 9, 55),
            ]
        )

        self.assertIn("DEADLINE_RISK", [diag.code for diag in diagnostics])

    def test_context_switching_is_detected(self) -> None:
        diagnostics, _ = lint_events(
            [
                build_lint_event("A", 9, 0, 9, 20, project_id="p1", tags=["one", "two"]),
                build_lint_event("B", 9, 20, 9, 40, project_id="p2", tags=["three", "four"]),
                build_lint_event("C", 9, 40, 10, 0, project_id="p3", tags=["five"]),
                build_lint_event("D", 10, 0, 10, 20, project_id="p4", tags=["six"]),
            ]
        )

        self.assertIn("CONTEXT_SWITCHING", [diag.code for diag in diagnostics])

    def test_summary_contains_counts_and_top_issues(self) -> None:
        diagnostics, summary = lint_events(
            [
                build_lint_event("A", 9, 0, 10, 0),
                build_lint_event("B", 9, 30, 10, 30),
                build_lint_event("C", 10, 45, 11, 0),
            ]
        )

        self.assertGreaterEqual(summary.severity_counts[DiagnosticSeverity.ERROR], 1)
        self.assertEqual(summary.top_blocking_issues[0].code, diagnostics[0].code)


if __name__ == "__main__":
    unittest.main()
