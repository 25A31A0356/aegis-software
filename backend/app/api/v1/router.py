"""
AEGIS UNIFIED DATA CORE - Master API v1 Router
Aggregates all multi-hazard, weather, telemetry, source management, and admin routes.
"""
from fastapi import APIRouter
from backend.app.api.v1.weather import router as weather_router
from backend.app.api.v1.hazards import router as hazards_router
from backend.app.api.v1.alerts import router as alerts_router
from backend.app.api.v1.earthquakes import router as earthquakes_router
from backend.app.api.v1.floods import router as floods_router
from backend.app.api.v1.cyclones import router as cyclones_router
from backend.app.api.v1.lightning import router as lightning_router
from backend.app.api.v1.wildfires import router as wildfires_router
from backend.app.api.v1.air_quality import router as air_quality_router
from backend.app.api.v1.sources import router as sources_router
from backend.app.api.v1.correlation import router as correlation_router
from backend.app.api.v1.ai import router as ai_router
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.admin import router as admin_router
from backend.app.api.v1.sos import router as sos_router
from backend.app.api.v1.reports import router as reports_router
from backend.app.api.v1.mobile import router as mobile_router

api_router = APIRouter()

api_router.include_router(weather_router)
api_router.include_router(hazards_router)
api_router.include_router(alerts_router)
api_router.include_router(earthquakes_router)
api_router.include_router(floods_router)
api_router.include_router(cyclones_router)
api_router.include_router(lightning_router)
api_router.include_router(wildfires_router)
api_router.include_router(air_quality_router)
api_router.include_router(sources_router)
api_router.include_router(correlation_router)
api_router.include_router(ai_router)
api_router.include_router(health_router)
api_router.include_router(admin_router)
api_router.include_router(sos_router)
api_router.include_router(reports_router)
api_router.include_router(mobile_router)
