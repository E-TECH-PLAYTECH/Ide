from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache


class Environment(StrEnum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


_DEFAULT_DATABASE_URLS: dict[Environment, str] = {
    Environment.DEV: "sqlite:///lifeos-dev.db",
    Environment.TEST: "sqlite:///lifeos-test.db",
}


@dataclass(frozen=True)
class Settings:
    environment: Environment
    database_url: str
    host: str
    port: int
    log_level: str
    log_format: str



def _get_environment() -> Environment:
    value = os.environ.get("LIFEOS_ENV", Environment.DEV).strip().lower()
    try:
        return Environment(value)
    except ValueError as exc:
        valid = ", ".join(env.value for env in Environment)
        raise ValueError(f"LIFEOS_ENV must be one of: {valid}") from exc



def _get_database_url(environment: Environment) -> str:
    explicit_url = os.environ.get("LIFEOS_DATABASE_URL")
    if explicit_url:
        return explicit_url

    if environment is Environment.PROD:
        raise ValueError(
            "LIFEOS_DATABASE_URL must be set when LIFEOS_ENV=prod. "
            "Run migrations before starting the app."
        )

    return _DEFAULT_DATABASE_URLS[environment]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    environment = _get_environment()
    return Settings(
        environment=environment,
        database_url=_get_database_url(environment),
        host=os.environ.get("LIFEOS_HOST", "0.0.0.0"),
        port=int(os.environ.get("LIFEOS_PORT", "8000")),
        log_level=os.environ.get("LIFEOS_LOG_LEVEL", "INFO").upper(),
        log_format=os.environ.get("LIFEOS_LOG_FORMAT", "json").strip().lower(),
    )


# Backwards-compatible helpers used throughout existing code.
def get_environment() -> Environment:
    return get_settings().environment



def get_database_url() -> str:
    return get_settings().database_url
