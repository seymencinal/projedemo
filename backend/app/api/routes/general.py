from fastapi import APIRouter

from app.core.config import get_settings

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


@router.get("/health")
def read_health() -> dict[str, str]:
    return {"status": "healthy"}
