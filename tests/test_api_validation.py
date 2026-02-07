from __future__ import annotations

import json
import os
import socket
import subprocess
import tempfile
import time
import unittest
from urllib import error, request


class ApiValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.port = self._get_free_port()
        env = os.environ.copy()
        env["LIFEOS_DATABASE_URL"] = f"sqlite:///{self.temp_db.name}"
        self.server = subprocess.Popen(
            [
                "python",
                "-m",
                "uvicorn",
                "lifeos.api:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._wait_for_server()

    def tearDown(self) -> None:
        self.server.terminate()
        self.server.wait(timeout=5)
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def _get_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def _wait_for_server(self) -> None:
        health_url = f"http://127.0.0.1:{self.port}/health"
        for _ in range(50):
            try:
                with request.urlopen(health_url, timeout=0.2) as response:
                    if response.status == 200:
                        return
            except Exception:
                time.sleep(0.1)
        self.fail("Server did not start in time")

    def _post_json(self, path: str, payload: dict) -> tuple[int, dict]:
        req = request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=1) as response:
                body = json.loads(response.read().decode("utf-8"))
                return response.status, body
        except error.HTTPError as exc:
            body = json.loads(exc.read().decode("utf-8"))
            return exc.code, body

    def _request_json(
        self, path: str, method: str = "GET", payload: dict | list | None = None
    ) -> tuple[int, dict | list | None]:
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with request.urlopen(req, timeout=1) as response:
                raw = response.read().decode("utf-8")
                body = json.loads(raw) if raw else None
                return response.status, body
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            body = json.loads(raw) if raw else None
            return exc.code, body

    def test_create_event_with_reversed_time_range_returns_422(self) -> None:
        payload = {
            "id": "event-1",
            "content": "Morning run",
            "tags": ["health"],
            "start_time": "2024-01-10T10:00:00",
            "end_time": "2024-01-10T09:00:00",
            "is_fixed": False,
        }

        status_code, _ = self._post_json("/events", payload)

        self.assertEqual(status_code, 422)

    def test_create_task_with_non_positive_duration_returns_422(self) -> None:
        base_payload = {
            "id": "task-1",
            "content": "Write report",
            "tags": ["work"],
            "status": "TODO",
            "deadline": "2024-01-11T09:00:00",
            "dependency_ids": [],
        }

        zero_status_code, _ = self._post_json(
            "/tasks", {**base_payload, "estimated_duration_minutes": 0}
        )
        negative_status_code, _ = self._post_json(
            "/tasks", {**base_payload, "estimated_duration_minutes": -15}
        )

        self.assertEqual(zero_status_code, 422)
        self.assertEqual(negative_status_code, 422)

    def test_create_event_with_empty_content_returns_422(self) -> None:
        payload = {
            "id": "event-2",
            "content": "   ",
            "tags": ["health"],
            "start_time": "2024-01-10T08:00:00",
            "end_time": "2024-01-10T09:00:00",
            "is_fixed": False,
        }

        status_code, _ = self._post_json("/events", payload)

        self.assertEqual(status_code, 422)

    def test_create_task_with_empty_status_returns_422(self) -> None:
        payload = {
            "id": "task-2",
            "content": "Book flight",
            "tags": ["travel"],
            "status": "   ",
            "deadline": None,
            "estimated_duration_minutes": 30,
            "dependency_ids": [],
        }

        status_code, _ = self._post_json("/tasks", payload)

        self.assertEqual(status_code, 422)


    def test_task_crud_dependencies_and_project_scoped_query(self) -> None:
        status_code, _ = self._post_json(
            "/tasks",
            {
                "id": "dep-1",
                "content": "Draft outline",
                "tags": ["work"],
                "status": "TODO",
                "deadline": "2024-01-10T09:00:00",
                "estimated_duration_minutes": 30,
                "project_id": "project-1",
                "dependency_ids": [],
            },
        )
        self.assertEqual(status_code, 201)

        status_code, _ = self._post_json(
            "/tasks",
            {
                "id": "task-1",
                "content": "Write draft",
                "tags": ["work", "writing"],
                "status": "TODO",
                "deadline": "2024-01-10T11:00:00",
                "estimated_duration_minutes": 60,
                "project_id": "project-1",
                "dependency_ids": ["dep-1"],
            },
        )
        self.assertEqual(status_code, 201)

        status_code, body = self._request_json("/tasks/task-1/dependencies")
        self.assertEqual(status_code, 200)
        self.assertEqual(body, ["dep-1"])

        status_code, body = self._request_json(
            "/tasks/task-1/dependencies", method="PUT", payload=[]
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(body, [])

        status_code, body = self._request_json(
            "/projects/project-1/tasks?status=TODO&limit=1&offset=0"
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["project_id"], "project-1")

        status_code, _ = self._request_json("/tasks/task-1", method="DELETE")
        self.assertEqual(status_code, 204)

    def test_event_filters_and_error_shape(self) -> None:
        status_code, _ = self._post_json(
            "/events",
            {
                "id": "event-a",
                "content": "Daily standup",
                "tags": ["team"],
                "start_time": "2024-01-10T09:00:00",
                "end_time": "2024-01-10T09:30:00",
                "is_fixed": True,
                "project_id": "project-1",
            },
        )
        self.assertEqual(status_code, 201)

        status_code, body = self._request_json(
            "/events?is_fixed=true&project_id=project-1&limit=1&offset=0"
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["id"], "event-a")

        status_code, body = self._request_json("/events/missing-event")
        self.assertEqual(status_code, 404)
        self.assertEqual(body["error"]["code"], "not_found")

    def test_lint_accepts_payload_only_event_shape(self) -> None:
        payload = {
            "events": [
                {
                    "id": "event-1",
                    "start_time": "2024-01-10T09:00:00",
                    "end_time": "2024-01-10T10:00:00",
                },
                {
                    "id": "event-2",
                    "start_time": "2024-01-10T09:30:00",
                    "end_time": "2024-01-10T10:30:00",
                },
            ]
        }

        status_code, body = self._post_json("/lint", payload)

        self.assertEqual(status_code, 200)
        self.assertEqual(len(body["diagnostics"]), 1)
        self.assertEqual(body["diagnostics"][0]["event_id"], "event-2")

    def test_lint_ignores_extra_event_fields_for_compatibility(self) -> None:
        payload = {
            "events": [
                {
                    "id": "event-3",
                    "content": "Focus block",
                    "tags": ["deep-work"],
                    "is_fixed": False,
                    "start_time": "2024-01-10T13:00:00",
                    "end_time": "2024-01-10T14:00:00",
                },
                {
                    "id": "event-4",
                    "content": "Break",
                    "tags": ["rest"],
                    "is_fixed": False,
                    "start_time": "2024-01-10T13:20:00",
                    "end_time": "2024-01-10T13:40:00",
                },
            ]
        }

        status_code, body = self._post_json("/lint", payload)

        self.assertEqual(status_code, 200)
        self.assertEqual(len(body["diagnostics"]), 1)
        self.assertEqual(body["diagnostics"][0]["event_id"], "event-4")


if __name__ == "__main__":
    unittest.main()
