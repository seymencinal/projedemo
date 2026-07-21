from fastapi import APIRouter

from app.api.routes.companies import router as companies_router
from app.api.routes.general import router as general_router

api_router = APIRouter()
api_router.include_router(general_router)
api_router.include_router(companies_router)
