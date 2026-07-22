from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.research import get_research_service
from app.api.exception_handlers import register_exception_handlers
from app.api.routes.researches import router
from app.exceptions.research import ResearchNotFoundError
from app.models.research import Research, ResearchStatus
from app.repositories.research import ResearchRepository
from app.schemas.research import ResearchCreate, ResearchRead, ResearchUpdate
from app.services.research import ResearchService

ORGANIZATION_ID = uuid4()


def research() -> Research:
    item = Research(organization_id=ORGANIZATION_ID, name="Example", status=ResearchStatus.DRAFT)
    item.id = uuid4()
    item.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    item.updated_at = item.created_at
    return item


def test_research_schemas_validate_names_status_and_read_model() -> None:
    create = ResearchCreate(name=" Example ", description=None)
    update = ResearchUpdate(name=" Updated ", status=ResearchStatus.ACTIVE)
    item = research()
    read = ResearchRead.model_validate(item)
    assert create.name == "Example" and create.description is None
    assert update.name == "Updated" and update.status is ResearchStatus.ACTIVE
    assert read.id == item.id and read.organization_id == ORGANIZATION_ID
    for value in ("", "   "):
        with pytest.raises(ValidationError):
            ResearchCreate(name=value)
    with pytest.raises(ValidationError):
        ResearchCreate(name="x", status="bad")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_research_repository_scopes_queries_and_mutates() -> None:
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none.return_value = research()
    result.scalars.return_value.all.return_value = [research()]
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    repository = ResearchRepository(session)
    assert await repository.get(uuid4(), ORGANIZATION_ID) is not None
    assert await repository.list(ORGANIZATION_ID)
    item = research()
    assert await repository.add(item) is item
    await repository.delete(item)
    assert ORGANIZATION_ID in session.execute.await_args.args[0].compile().params.values()


@pytest.mark.asyncio
async def test_research_service_crud_and_tenant_isolation() -> None:
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    repository = MagicMock(spec=ResearchRepository)
    repository.add = AsyncMock(side_effect=lambda value: value)
    repository.list = AsyncMock(return_value=[research()])
    repository.get = AsyncMock(return_value=research())
    repository.delete = AsyncMock()
    service = ResearchService(session, repository)
    created = await service.create(ORGANIZATION_ID, ResearchCreate(name="Example"))
    assert created.organization_id == ORGANIZATION_ID
    assert await service.list(ORGANIZATION_ID)
    item = await service.get(created.id, ORGANIZATION_ID)
    await service.update(item.id, ORGANIZATION_ID, ResearchUpdate(name="Updated"))
    await service.delete(item.id, ORGANIZATION_ID)
    repository.get = AsyncMock(return_value=None)
    with pytest.raises(ResearchNotFoundError):
        await service.get(uuid4(), uuid4())


def test_research_api_crud_validation_and_tenant_context() -> None:
    service = MagicMock(spec=ResearchService)
    item = research()
    service.create = AsyncMock(return_value=item)
    service.list = AsyncMock(return_value=[item])
    service.get = AsyncMock(return_value=item)
    service.update = AsyncMock(return_value=item)
    service.delete = AsyncMock()
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_research_service] = lambda: service
    client = TestClient(app)
    headers = {"X-Organization-ID": str(ORGANIZATION_ID)}
    assert client.post("/researches", headers=headers, json={"name": "Example"}).status_code == 201
    assert client.get("/researches", headers=headers).status_code == 200
    assert client.get(f"/researches/{item.id}", headers=headers).status_code == 200
    assert (
        client.patch(
            f"/researches/{item.id}", headers=headers, json={"name": "Updated"}
        ).status_code
        == 200
    )
    assert client.delete(f"/researches/{item.id}", headers=headers).status_code == 204
    assert client.post("/researches", json={"name": "Example"}).status_code == 422
    assert client.post("/researches", headers=headers, json={"name": " "}).status_code == 422
    service.get.side_effect = ResearchNotFoundError(item.id)
    assert client.get(f"/researches/{item.id}", headers=headers).status_code == 404
