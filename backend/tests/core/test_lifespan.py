import logging
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.lifespan import lifespan


def test_lifespan_logs_startup_and_shutdown(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = FastAPI(
        title="Test API",
        version="9.9.9",
        lifespan=lifespan,
    )
    caplog.set_level(logging.INFO, logger="app.core.lifespan")

    with TestClient(app):
        assert any(record.message == "application_started" for record in caplog.records)

    assert any(record.message == "application_stopped" for record in caplog.records)

    startup_record = next(
        record for record in caplog.records if record.message == "application_started"
    )
    shutdown_record = next(
        record for record in caplog.records if record.message == "application_stopped"
    )

    assert startup_record.__dict__["app_name"] == "Test API"
    assert startup_record.__dict__["app_version"] == "9.9.9"
    assert shutdown_record.__dict__["app_name"] == "Test API"
    assert shutdown_record.__dict__["app_version"] == "9.9.9"


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_lifespan_rejects_production_without_database_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("DATABASE_USER", raising=False)
    monkeypatch.delenv("DATABASE_PASSWORD", raising=False)
    app = FastAPI(lifespan=lifespan)

    with (
        pytest.raises(ValidationError, match="Database credentials must be configured"),
        TestClient(app),
    ):
        pass
