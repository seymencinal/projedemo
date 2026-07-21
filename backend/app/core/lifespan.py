from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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
        logger.info(
            "application_stopped",
            extra={
                "app_name": app.title,
                "app_version": app.version,
            },
        )
