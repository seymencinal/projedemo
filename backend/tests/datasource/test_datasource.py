from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.research import get_datasource_service
from app.api.exception_handlers import register_exception_handlers
from app.api.routes.datasources import router as datasources_router
from app.api.routes.researches import router as researches_router
from app.exceptions.research import DatasourceNotFoundError, ResearchNotFoundError
from app.models.datasource import Datasource, DatasourceStatus, DatasourceType
from app.models.research import Research
from app.repositories.datasource import DatasourceRepository
from app.repositories.research import ResearchRepository
from app.schemas.datasource import DatasourceCreate, DatasourceRead, DatasourceUpdate
from app.services.datasource import DatasourceService

ORG = uuid4()
RESEARCH_ID = uuid4()


def datasource() -> Datasource:
    item = Datasource(
        organization_id=ORG,
        research_id=RESEARCH_ID,
        name="Source",
        source_type=DatasourceType.CSV,
        status=DatasourceStatus.PENDING,
        configuration={"delimiter": ","},
    )
    item.id = uuid4()
    item.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    item.updated_at = item.created_at
    return item


def test_datasource_schemas_validate_types_names_json_and_read() -> None:
    create = DatasourceCreate(
        name=" Source ", source_type=DatasourceType.CSV, configuration={"x": 1}
    )
    update = DatasourceUpdate(name=" Updated ", status=DatasourceStatus.READY, configuration={})
    assert create.name == "Source" and update.status is DatasourceStatus.READY
    assert DatasourceRead.model_validate(datasource()).configuration == {"delimiter": ","}
    for value in ("", "   "):
        with pytest.raises(ValidationError):
            DatasourceCreate(name=value, source_type=DatasourceType.CSV)
    with pytest.raises(ValidationError):
        DatasourceCreate(name="x", source_type="invalid")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        DatasourceCreate(name="x", source_type="csv", configuration=[])  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_datasource_repository_scopes_parent_and_tenant_queries() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = datasource()
    result.scalars.return_value.all.return_value = [datasource()]
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    repository = DatasourceRepository(session)
    assert await repository.get(uuid4(), ORG) is not None
    assert await repository.list(RESEARCH_ID, ORG)
    item = datasource()
    assert await repository.add(item) is item
    await repository.delete(item)
    assert ORG in session.execute.await_args.args[0].compile().params.values()


@pytest.mark.asyncio
async def test_datasource_service_crud_parent_validation_and_isolation() -> None:
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    repository = MagicMock(spec=DatasourceRepository)
    research_repository = MagicMock(spec=ResearchRepository)
    research_repository.get = AsyncMock(return_value=Research(organization_id=ORG, name="Research"))
    repository.add = AsyncMock(side_effect=lambda value: value)
    repository.list = AsyncMock(return_value=[datasource()])
    repository.get = AsyncMock(return_value=datasource())
    repository.delete = AsyncMock()
    service = DatasourceService(session, repository, research_repository)
    created = await service.create(
        RESEARCH_ID, ORG, DatasourceCreate(name="Source", source_type=DatasourceType.CSV)
    )
    assert created.organization_id == ORG
    assert await service.list(RESEARCH_ID, ORG)
    item = await service.get(created.id, ORG)
    await service.update(item.id, ORG, DatasourceUpdate(status=DatasourceStatus.DISABLED))
    await service.delete(item.id, ORG)
    research_repository.get = AsyncMock(return_value=None)
    with pytest.raises(ResearchNotFoundError):
        await service.create(
            RESEARCH_ID, uuid4(), DatasourceCreate(name="x", source_type=DatasourceType.CSV)
        )
    repository.get = AsyncMock(return_value=None)
    with pytest.raises(DatasourceNotFoundError):
        await service.get(uuid4(), uuid4())


def test_datasource_api_crud_parent_routes_validation_and_tenant_header() -> None:
    service = MagicMock(spec=DatasourceService)
    item = datasource()
    service.create = AsyncMock(return_value=item)
    service.list = AsyncMock(return_value=[item])
    service.get = AsyncMock(return_value=item)
    service.update = AsyncMock(return_value=item)
    service.delete = AsyncMock()
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(researches_router)
    app.include_router(datasources_router)
    app.dependency_overrides[get_datasource_service] = lambda: service
    client = TestClient(app)
    headers = {"X-Organization-ID": str(ORG)}
    assert (
        client.post(
            f"/researches/{RESEARCH_ID}/datasources",
            headers=headers,
            json={"name": "Source", "source_type": "csv"},
        ).status_code
        == 201
    )
    assert client.get(f"/researches/{RESEARCH_ID}/datasources", headers=headers).status_code == 200
    assert client.get(f"/datasources/{item.id}", headers=headers).status_code == 200
    assert (
        client.patch(
            f"/datasources/{item.id}", headers=headers, json={"status": "disabled"}
        ).status_code
        == 200
    )
    assert client.delete(f"/datasources/{item.id}", headers=headers).status_code == 204
    assert (
        client.post(
            f"/researches/{RESEARCH_ID}/datasources", json={"name": "Source", "source_type": "csv"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/researches/{RESEARCH_ID}/datasources",
            headers=headers,
            json={"name": " ", "source_type": "csv"},
        ).status_code
        == 422
    )
    service.get.side_effect = DatasourceNotFoundError(item.id)
    assert client.get(f"/datasources/{item.id}", headers=headers).status_code == 404
