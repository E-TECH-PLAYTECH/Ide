from __future__ import annotations

import os
from enum import StrEnum


class Environment(StrEnum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


_DEFAULT_DATABASE_URLS: dict[Environment, str] = {
    Environment.DEV: "sqlite:///lifeos-dev.db",
    Environment.TEST: "sqlite:///lifeos-test.db",
}


def get_environment() -> Environment:
    value = os.environ.get("LIFEOS_ENV", Environment.DEV).strip().lower()
    try:
        return Environment(value)
    except ValueError as exc:
        valid = ", ".join(env.value for env in Environment)
        raise ValueError(f"LIFEOS_ENV must be one of: {valid}") from exc


def get_database_url() -> str:
    explicit_url = os.environ.get("LIFEOS_DATABASE_URL")
    if explicit_url:
        return explicit_url

    environment = get_environment()
    if environment is Environment.PROD:
        raise ValueError(
            "LIFEOS_DATABASE_URL must be set when LIFEOS_ENV=prod. "
            "Run migrations before starting the app."
        )

    return _DEFAULT_DATABASE_URLS[environment]
