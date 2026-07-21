from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies.database import get_database_resources
from app.core.config import get_settings
from app.db.session import DatabaseResources
from app.schemas.health import LivenessResponse, ReadinessResponse

router = APIRouter(tags=["general"])


@router.get("/")
def read_root() -> dict[str, str]:
    settings = get_settings()

    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment.value,
        "status": "ok",
    }


DatabaseResourcesDependency = Annotated[
    DatabaseResources | None,
    Depends(get_database_resources),
]


@router.get("/health", response_model=LivenessResponse)
def read_health() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
async def read_readiness(
    database: DatabaseResourcesDependency,
) -> ReadinessResponse:
    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable.",
        )

    try:
        async with database.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable.",
        ) from error

    return ReadinessResponse(status="ready")
