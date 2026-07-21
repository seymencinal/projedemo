from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import create_database_resources, dispose_database_resources

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    database = create_database_resources(get_settings())
    app.state.database = database

    logger.info(
        "application_started",
        extra={
            "app_name": app.title,
            "app_version": app.version,
        },
    )

    try:
        yield
    finally:
        await dispose_database_resources(database)
        del app.state.database
        logger.info(
            "application_stopped",
            extra={
                "app_name": app.title,
                "app_version": app.version,
            },
        )
