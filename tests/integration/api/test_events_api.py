from __future__ import annotations

from tests.support.api_harness import ApiIntegrationTestCase
from tests.support.fixtures import build_event_payload


class EventApiIntegrationTests(ApiIntegrationTestCase):
    def test_event_full_crud_and_conflict(self) -> None:
        payload = build_event_payload(
            event_id="event-1",
            start_time="2024-01-10T09:00:00",
            end_time="2024-01-10T10:00:00",
            project_id="project-1",
            tags=["focus"],
            is_fixed=True,
        )

        status_code, body = self.post_json("/events", payload)
        self.assertEqual(status_code, 201)
        self.assertEqual(body["id"], "event-1")

        duplicate_status, duplicate_body = self.post_json("/events", payload)
        self.assertEqual(duplicate_status, 409)
        self.assertEqual(duplicate_body["error"]["code"], "conflict")

        get_status, get_body = self.request_json("/events/event-1")
        self.assertEqual(get_status, 200)
        self.assertEqual(get_body["project_id"], "project-1")

        update_status, update_body = self.request_json(
            "/events/event-1",
            method="PUT",
            payload={
                "content": "Updated",
                "tags": ["review"],
                "start_time": "2024-01-10T10:00:00",
                "end_time": "2024-01-10T11:00:00",
                "is_fixed": False,
                "project_id": "project-2",
            },
        )
        self.assertEqual(update_status, 200)
        self.assertEqual(update_body["project_id"], "project-2")

        delete_status, _ = self.request_json("/events/event-1", method="DELETE")
        self.assertEqual(delete_status, 204)

        missing_status, missing_body = self.request_json("/events/event-1")
        self.assertEqual(missing_status, 404)
        self.assertEqual(missing_body["error"]["code"], "not_found")

    def test_event_filtering_and_pagination(self) -> None:
        events = [
            build_event_payload("event-a", "2024-01-10T09:00:00", "2024-01-10T09:30:00", project_id="project-1", tags=["team"], is_fixed=True),
            build_event_payload("event-b", "2024-01-10T10:00:00", "2024-01-10T11:00:00", project_id="project-1", tags=["focus"], is_fixed=False),
            build_event_payload("event-c", "2024-01-10T12:00:00", "2024-01-10T13:00:00", project_id="project-2", tags=["team"], is_fixed=True),
        ]
        for payload in events:
            status_code, _ = self.post_json("/events", payload)
            self.assertEqual(status_code, 201)

        filtered_status, filtered_body = self.request_json(
            "/events?project_id=project-1&is_fixed=true&limit=10&offset=0"
        )
        self.assertEqual(filtered_status, 200)
        self.assertEqual([item["id"] for item in filtered_body], ["event-a"])

        paged_status, paged_body = self.request_json("/events?limit=1&offset=1")
        self.assertEqual(paged_status, 200)
        self.assertEqual(len(paged_body), 1)
        self.assertEqual(paged_body[0]["id"], "event-b")
