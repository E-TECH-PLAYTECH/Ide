from __future__ import annotations

import unittest
from datetime import datetime

from lifeos.models import Diagnostic, DiagnosticSeverity, LintRequest, LintResponse, LintSummary


class LintContractRegressionTests(unittest.TestCase):
    def test_lint_request_accepts_event_only_shape(self) -> None:
        payload = {
            "events": [
                {
                    "id": "event-1",
                    "start_time": "2024-01-10T09:00:00",
                    "end_time": "2024-01-10T10:00:00",
                }
            ]
        }

        request_model = LintRequest.model_validate(payload)

        self.assertEqual(request_model.events[0].id, "event-1")
        self.assertEqual(request_model.events[0].dependency_ids, [])

    def test_lint_request_ignores_legacy_extra_fields(self) -> None:
        payload = {
            "events": [
                {
                    "id": "event-1",
                    "start_time": "2024-01-10T09:00:00",
                    "end_time": "2024-01-10T10:00:00",
                    "content": "legacy field",
                    "is_fixed": False,
                }
            ]
        }

        request_model = LintRequest.model_validate(payload)
        serialized = request_model.model_dump()

        self.assertNotIn("content", serialized["events"][0])
        self.assertNotIn("is_fixed", serialized["events"][0])

    def test_lint_response_serialization_keeps_summary(self) -> None:
        response_model = LintResponse(
            diagnostics=[
                Diagnostic(
                    code="OVERLAP",
                    severity=DiagnosticSeverity.ERROR,
                    message="Schedule overlap detected",
                    start=datetime(2024, 1, 10, 9, 30),
                    event_id="event-2",
                )
            ],
            summary=LintSummary(
                severity_counts={DiagnosticSeverity.ERROR: 1},
                top_blocking_issues=[],
            ),
        )

        serialized = response_model.model_dump(mode="json")

        self.assertIn("summary", serialized)
        self.assertEqual(serialized["summary"]["severity_counts"]["ERROR"], 1)


if __name__ == "__main__":
    unittest.main()
