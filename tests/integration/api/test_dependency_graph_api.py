from __future__ import annotations

from tests.support.api_harness import ApiIntegrationTestCase
from tests.support.fixtures import build_task_payload


class DependencyGraphIntegrationTests(ApiIntegrationTestCase):
    def test_dependency_graph_must_remain_acyclic(self) -> None:
        for payload in (
            build_task_payload("task-a"),
            build_task_payload("task-b", dependency_ids=["task-a"]),
            build_task_payload("task-c", dependency_ids=["task-b"]),
        ):
            status_code, _ = self.post_json("/tasks", payload)
            self.assertEqual(status_code, 201)

        cycle_status, cycle_body = self.request_json(
            "/tasks/task-a/dependencies",
            method="PUT",
            payload=["task-c"],
        )
        self.assertEqual(cycle_status, 422)
        self.assertEqual(cycle_body["error"]["code"], "validation_error")

    def test_blocked_when_dependency_task_missing(self) -> None:
        status_code, body = self.post_json(
            "/tasks",
            build_task_payload("task-1", dependency_ids=["does-not-exist"]),
        )
        self.assertEqual(status_code, 422)
        self.assertEqual(body["error"]["details"]["dependency_ids"], ["does-not-exist"])

    def test_dependency_cleanup_propagates_on_delete(self) -> None:
        for payload in (
            build_task_payload("dep-task"),
            build_task_payload("main-task", dependency_ids=["dep-task"]),
        ):
            status_code, _ = self.post_json("/tasks", payload)
            self.assertEqual(status_code, 201)

        delete_status, _ = self.request_json("/tasks/dep-task", method="DELETE")
        self.assertEqual(delete_status, 204)

        dep_status, dep_body = self.request_json("/tasks/main-task/dependencies")
        self.assertEqual(dep_status, 200)
        self.assertEqual(dep_body, [])
