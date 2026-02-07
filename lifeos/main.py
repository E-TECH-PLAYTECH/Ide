from __future__ import annotations

import uvicorn

from .api import app
from .settings import get_settings


def run() -> None:
    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    run()
