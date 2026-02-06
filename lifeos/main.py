from __future__ import annotations

import os

import uvicorn

from .api import app


def run() -> None:
    host = os.environ.get("LIFEOS_HOST", "0.0.0.0")
    port = int(os.environ.get("LIFEOS_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run()
