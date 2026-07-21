from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies.database import get_database_resources
from app.api.routes.general import router
from app.db.session import DatabaseResources


def create_test_client(database: DatabaseResources | None) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_database_resources] = lambda: database
    return TestClient(app)


def create_database_resources() -> tuple[DatabaseResources, MagicMock, MagicMock]:
    connection = MagicMock()
    connection.execute = AsyncMock()
    connection_context = MagicMock()
    connection_context.__aenter__ = AsyncMock(return_value=connection)
    connection_context.__aexit__ = AsyncMock(return_value=None)
    engine = MagicMock()
    engine.connect.return_value = connection_context
    database = DatabaseResources(
        engine=engine,
        session_factory=MagicMock(),
    )
    return database, engine, connection


def test_liveness_returns_ok_without_database_resource() -> None:
    client = create_test_client(None)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_ready_when_database_is_available() -> None:
    database, engine, connection = create_database_resources()
    client = create_test_client(database)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    engine.connect.assert_called_once_with()
    connection.execute.assert_awaited_once()


def test_readiness_returns_service_unavailable_without_database_resource() -> None:
    client = create_test_client(None)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Service unavailable."}


def test_readiness_does_not_expose_database_errors() -> None:
    database, engine, _ = create_database_resources()
    engine.connect.side_effect = SQLAlchemyError("database password is secret")
    client = create_test_client(database)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Service unavailable."}
    assert "secret" not in response.text
