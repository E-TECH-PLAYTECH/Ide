from __future__ import annotations

from tests.support.api_harness import ApiIntegrationTestCase


class PlanApiIntegrationTests(ApiIntegrationTestCase):
    def test_overloaded_day_returns_unmet_warning(self) -> None:
        status_code, body = self.post_json(
            "/plan",
            {
                "window_start": "2024-01-01T09:00:00",
                "window_end": "2024-01-01T17:00:00",
                "focus_hours_start": 9,
                "focus_hours_end": 17,
                "max_planned_minutes_per_day": 180,
                "tasks": [
                    {
                        "id": "task-a",
                        "content": "Task A",
                        "estimated_duration_minutes": 120,
                        "deadline": "2024-01-01T16:00:00",
                        "dependency_ids": [],
                    },
                    {
                        "id": "task-b",
                        "content": "Task B",
                        "estimated_duration_minutes": 120,
                        "deadline": "2024-01-01T16:00:00",
                        "dependency_ids": [],
                    },
                ],
                "fixed_events": [],
                "dependency_graph": {},
            },
        )
        self.assertEqual(status_code, 200)
        self.assertEqual([block["ref_id"] for block in body["blocks"]], ["task-a", "task-b"])
        self.assertEqual(len(body["unmet_task_warnings"]), 1)
        self.assertEqual(body["unmet_task_warnings"][0]["task_id"], "task-b")
        self.assertEqual(body["unmet_task_warnings"][0]["minutes_unplanned"], 60)

    def test_dependencies_block_tasks_until_predecessors_are_done(self) -> None:
        status_code, body = self.post_json(
            "/plan",
            {
                "window_start": "2024-01-01T09:00:00",
                "window_end": "2024-01-01T12:00:00",
                "focus_hours_start": 9,
                "focus_hours_end": 12,
                "max_planned_minutes_per_day": 180,
                "tasks": [
                    {
                        "id": "prepare",
                        "content": "Prepare",
                        "estimated_duration_minutes": 120,
                        "deadline": "2024-01-01T12:00:00",
                        "dependency_ids": [],
                    },
                    {
                        "id": "ship",
                        "content": "Ship",
                        "estimated_duration_minutes": 120,
                        "deadline": "2024-01-01T11:30:00",
                        "dependency_ids": ["prepare"],
                    },
                ],
                "fixed_events": [],
                "dependency_graph": {"ship": ["prepare"]},
            },
        )
        self.assertEqual(status_code, 200)
        self.assertEqual([block["ref_id"] for block in body["blocks"]], ["prepare", "ship"])
        self.assertEqual(len(body["unmet_task_warnings"]), 1)
        self.assertEqual(body["unmet_task_warnings"][0]["task_id"], "ship")
        self.assertEqual(body["unmet_task_warnings"][0]["reason"], "Insufficient capacity before strict deadline.")

    def test_strict_deadline_creates_warning_when_capacity_exists_later(self) -> None:
        status_code, body = self.post_json(
            "/plan",
            {
                "window_start": "2024-01-01T09:00:00",
                "window_end": "2024-01-02T17:00:00",
                "focus_hours_start": 9,
                "focus_hours_end": 17,
                "max_planned_minutes_per_day": 240,
                "tasks": [
                    {
                        "id": "urgent",
                        "content": "Urgent",
                        "estimated_duration_minutes": 300,
                        "deadline": "2024-01-01T11:00:00",
                        "dependency_ids": [],
                    },
                    {
                        "id": "normal",
                        "content": "Normal",
                        "estimated_duration_minutes": 120,
                        "deadline": "2024-01-02T17:00:00",
                        "dependency_ids": [],
                    },
                ],
                "fixed_events": [
                    {
                        "id": "meeting",
                        "content": "Meeting",
                        "start_time": "2024-01-01T09:00:00",
                        "end_time": "2024-01-01T10:00:00",
                    }
                ],
                "dependency_graph": {},
            },
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(body["blocks"][0]["block_type"], "fixed_event")
        self.assertEqual(body["blocks"][0]["ref_id"], "meeting")
        warning_ids = [warning["task_id"] for warning in body["unmet_task_warnings"]]
        self.assertIn("urgent", warning_ids)
        urgent_warning = next(w for w in body["unmet_task_warnings"] if w["task_id"] == "urgent")
        self.assertEqual(urgent_warning["reason"], "Insufficient capacity before strict deadline.")
