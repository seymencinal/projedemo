from fastapi import APIRouter

from app.api.routes.companies import router as companies_router
from app.api.routes.datasources import router as datasources_router
from app.api.routes.general import router as general_router
from app.api.routes.organizations import router as organizations_router
from app.api.routes.researches import router as researches_router

api_router = APIRouter()
api_router.include_router(general_router)
api_router.include_router(organizations_router)
api_router.include_router(companies_router)
api_router.include_router(researches_router)
api_router.include_router(datasources_router)
