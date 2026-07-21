import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

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
