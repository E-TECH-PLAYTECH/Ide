from __future__ import annotations

import json
import os
import socket
import subprocess
import tempfile
import time
import unittest
from typing import Any
from urllib import error, request


class ApiIntegrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.port = self._get_free_port()
        env = os.environ.copy()
        env["LIFEOS_DATABASE_URL"] = f"sqlite:///{self.temp_db.name}"
        env["LIFEOS_ENV"] = "test"

        subprocess.run(
            ["python", "-m", "alembic", "upgrade", "head"],
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
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

    def request_json(
        self, path: str, method: str = "GET", payload: dict[str, Any] | list[Any] | None = None
    ) -> tuple[int, Any]:
        data = None
        headers: dict[str, str] = {}
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

    def post_json(self, path: str, payload: dict[str, Any]) -> tuple[int, Any]:
        return self.request_json(path, method="POST", payload=payload)
