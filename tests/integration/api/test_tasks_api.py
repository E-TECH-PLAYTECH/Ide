from __future__ import annotations

from tests.support.api_harness import ApiIntegrationTestCase
from tests.support.fixtures import build_project_scenario, build_task_payload


class TaskApiIntegrationTests(ApiIntegrationTestCase):
    def test_task_full_crud_filter_pagination_and_conflict(self) -> None:
        dep, task = build_project_scenario("project-1")

        status_code, _ = self.post_json("/tasks", dep)
        self.assertEqual(status_code, 201)

        status_code, body = self.post_json("/tasks", task)
        self.assertEqual(status_code, 201)
        self.assertEqual(body["dependency_ids"], [dep["id"]])

        duplicate_status, duplicate_body = self.post_json("/tasks", task)
        self.assertEqual(duplicate_status, 409)
        self.assertEqual(duplicate_body["error"]["code"], "conflict")

        get_status, get_body = self.request_json(f"/tasks/{task['id']}")
        self.assertEqual(get_status, 200)
        self.assertEqual(get_body["project_id"], "project-1")

        update_status, update_body = self.request_json(
            f"/tasks/{task['id']}",
            method="PUT",
            payload=build_task_payload(
                task_id=task["id"],
                status="IN_PROGRESS",
                project_id="project-2",
                dependency_ids=[],
            ),
        )
        self.assertEqual(update_status, 200)
        self.assertEqual(update_body["status"], "IN_PROGRESS")
        self.assertEqual(update_body["dependency_ids"], [])

        filter_status, filter_body = self.request_json(
            "/tasks?project_id=project-2&status=IN_PROGRESS&limit=10&offset=0"
        )
        self.assertEqual(filter_status, 200)
        self.assertEqual([row["id"] for row in filter_body], [task["id"]])

        second_status, _ = self.post_json(
            "/tasks",
            build_task_payload(
                task_id="task-2",
                project_id="project-2",
                status="IN_PROGRESS",
                deadline="2024-01-22T10:00:00",
            ),
        )
        self.assertEqual(second_status, 201)

        paged_status, paged_body = self.request_json("/tasks?limit=1&offset=1")
        self.assertEqual(paged_status, 200)
        self.assertEqual(len(paged_body), 1)

        delete_status, _ = self.request_json(f"/tasks/{task['id']}", method="DELETE")
        self.assertEqual(delete_status, 204)

    def test_project_scoped_task_listing(self) -> None:
        dep, task = build_project_scenario("project-1")
        for payload in (dep, task):
            status_code, _ = self.post_json("/tasks", payload)
            self.assertEqual(status_code, 201)

        status_code, body = self.request_json(
            "/projects/project-1/tasks?status=TODO&limit=1&offset=0"
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["project_id"], "project-1")
