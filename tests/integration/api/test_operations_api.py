from __future__ import annotations

from tests.support.api_harness import ApiIntegrationTestCase


class OperationsApiIntegrationTests(ApiIntegrationTestCase):
    def test_liveness_and_readiness_endpoints(self) -> None:
        live_status, live_body = self.request_json("/health/live")
        self.assertEqual(live_status, 200)
        self.assertEqual(live_body, {"status": "ok"})

        ready_status, ready_body = self.request_json("/health/ready")
        self.assertEqual(ready_status, 200)
        self.assertEqual(ready_body, {"status": "ready"})

    def test_request_id_header_is_propagated(self) -> None:
        status, _, headers = self.request_json_with_headers(
            "/health/live",
            headers={"X-Request-ID": "req-123"},
        )
        self.assertEqual(status, 200)
        normalized = {key.lower(): value for key, value in headers.items()}
        self.assertEqual(normalized.get("x-request-id"), "req-123")

    def test_request_id_header_is_generated_when_missing(self) -> None:
        status, _, headers = self.request_json_with_headers("/health/live")
        self.assertEqual(status, 200)
        normalized = {key.lower(): value for key, value in headers.items()}
        self.assertIsNotNone(normalized.get("x-request-id"))
        self.assertNotEqual(normalized.get("x-request-id"), "")
