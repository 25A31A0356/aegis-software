"""
AEGIS CENTRAL DATA GATEWAY - Machine-Readable Discovery & Manifest API
/api/v1/discovery and /api/v1/manifest
Safely exposes non-secret metadata for Web & Mobile SDK auto-configuration.
"""
from typing import Dict, Any, List
from fastapi import APIRouter
from pydantic import BaseModel
from backend.app.core.config import settings
from backend.app.schemas.common import ApiResponse

router = APIRouter(tags=["API Discovery & Configuration"])


class EndpointInfo(BaseModel):
    path: str
    method: str
    category: str
    description: str
    access_level: str  # public, rate_limited, authenticated, admin_only
    client_target: List[str]


class GatewayManifest(BaseModel):
    service_name: str
    version: str
    api_base_path: str
    environment: str
    supported_data_categories: List[str]
    supported_client_types: List[str]
    authentication_mechanisms: List[Dict[str, str]]
    endpoints: List[EndpointInfo]
    rate_limits: Dict[str, Any]
    security_features: List[str]


ENDPOINTS_MANIFEST: List[EndpointInfo] = [
    EndpointInfo(path="/health", method="GET", category="SYSTEM", description="Root container health and readiness probe", access_level="public", client_target=["web", "app", "admin", "orchestrator"]),
    EndpointInfo(path="/api/v1/health", method="GET", category="SYSTEM", description="Detailed multi-component health and latency matrix", access_level="public", client_target=["admin", "monitoring"]),
    EndpointInfo(path="/api/v1/status", method="GET", category="SYSTEM", description="Live status of all 8 external provider adapters", access_level="public", client_target=["web", "app", "admin"]),
    EndpointInfo(path="/api/v1/discovery", method="GET", category="SYSTEM", description="Machine-readable API discovery manifest", access_level="public", client_target=["web", "app", "admin"]),
    EndpointInfo(path="/api/v1/weather", method="GET", category="WEATHER", description="Real-time normalized meteorological telemetry for coordinates", access_level="rate_limited", client_target=["web", "app"]),
    EndpointInfo(path="/api/v1/forecast", method="GET", category="WEATHER", description="Multi-day daily and 24-hour hourly forecast curves", access_level="rate_limited", client_target=["web", "app"]),
    EndpointInfo(path="/api/v1/hazards", method="GET", category="HAZARD", description="Multi-hazard observation catalog with categorical filtering", access_level="rate_limited", client_target=["web", "app"]),
    EndpointInfo(path="/api/v1/hazards/nearby", method="GET", category="HAZARD", description="Spatial search returning nearby hazards sorted by proximity", access_level="rate_limited", client_target=["web", "app"]),
    EndpointInfo(path="/api/v1/earthquakes", method="GET", category="EARTHQUAKE", description="Live USGS seismic events and depth telemetry", access_level="rate_limited", client_target=["web", "app"]),
    EndpointInfo(path="/api/v1/floods", method="GET", category="FLOOD", description="CWC river water levels, danger stages, and discharge trends", access_level="rate_limited", client_target=["web", "app"]),
    EndpointInfo(path="/api/v1/wildfires", method="GET", category="WILDFIRE", description="NASA FIRMS satellite thermal anomaly and active fire hotspots", access_level="rate_limited", client_target=["web", "app"]),
    EndpointInfo(path="/api/v1/cyclones", method="GET", category="CYCLONE", description="IMD & INCOIS cyclone intensity grades and forecast tracks", access_level="rate_limited", client_target=["web", "app"]),
    EndpointInfo(path="/api/v1/lightning", method="GET", category="LIGHTNING", description="Atmospheric electrical discharge telemetry", access_level="rate_limited", client_target=["web", "app"]),
    EndpointInfo(path="/api/v1/air-quality", method="GET", category="AIR_QUALITY", description="Ambient PM2.5, PM10, NO2, and composite AQI telemetry", access_level="rate_limited", client_target=["web", "app"]),
    EndpointInfo(path="/api/v1/alerts", method="GET", category="EMERGENCY", description="Official CAP-CP emergency disaster alerts and bulletins", access_level="rate_limited", client_target=["web", "app"]),
    EndpointInfo(path="/api/v1/location", method="GET", category="LOCATION", description="Combined geocoding search and reverse geocode resolver", access_level="rate_limited", client_target=["web", "app"]),
    EndpointInfo(path="/api/v1/location/search", method="GET", category="LOCATION", description="Forward geocoding place and city search", access_level="rate_limited", client_target=["web", "app"]),
    EndpointInfo(path="/api/v1/location/reverse", method="GET", category="LOCATION", description="Reverse geocode coordinates to district, state, elevation", access_level="rate_limited", client_target=["web", "app"]),
    EndpointInfo(path="/api/v1/mobile/sync", method="GET", category="MOBILE", description="Single-call low-bandwidth payload for mobile app synchronization", access_level="rate_limited", client_target=["app"]),
    EndpointInfo(path="/api/v1/sos", method="POST", category="EMERGENCY", description="Citizen emergency distress SOS signal submission", access_level="rate_limited", client_target=["web", "app"]),
    EndpointInfo(path="/api/v1/reports", method="POST", category="CROWDSOURCE", description="Citizen crowdsourced disaster incident report submission", access_level="rate_limited", client_target=["web", "app"]),
    EndpointInfo(path="/api/v1/auth/register", method="POST", category="AUTH", description="User registration for mobile and web clients", access_level="public", client_target=["web", "app"]),
    EndpointInfo(path="/api/v1/auth/login", method="POST", category="AUTH", description="User login and JWT bearer token issuance", access_level="public", client_target=["web", "app"]),
    EndpointInfo(path="/api/v1/admin/auth/login", method="POST", category="ADMIN", description="Administrative authentication and JWT token issuance", access_level="public", client_target=["admin"]),
    EndpointInfo(path="/api/v1/sources", method="GET", category="ADMIN", description="List configured external data sources and health states", access_level="admin_only", client_target=["admin"]),
    EndpointInfo(path="/api/v1/sources", method="POST", category="ADMIN", description="Register or update external data source with encrypted credentials", access_level="admin_only", client_target=["admin"]),
]


@router.get("/discovery", response_model=ApiResponse[GatewayManifest])
@router.get("/manifest", response_model=ApiResponse[GatewayManifest])
async def get_gateway_discovery():
    """
    Returns public, machine-readable gateway configuration and endpoint directory.
    Zero secrets, passwords, or provider API keys are included.
    """
    manifest = GatewayManifest(
        service_name="AEGIS Central Data Gateway",
        version=settings.VERSION,
        api_base_path=settings.API_V1_STR,
        environment=settings.ENVIRONMENT,
        supported_data_categories=[
            "WEATHER",
            "FORECAST",
            "EARTHQUAKE",
            "FLOOD",
            "WILDFIRE",
            "CYCLONE",
            "LIGHTNING",
            "AIR_QUALITY",
            "LOCATION",
            "EMERGENCY_ALERTS",
            "SOS_TRIAGE",
            "CROWDSOURCE_REPORTS"
        ],
        supported_client_types=["web", "app", "admin", "internal"],
        authentication_mechanisms=[
            {
                "type": "CLIENT_CONTEXT_HEADER",
                "header": "X-Aegis-Client",
                "description": "Identifies client platform context ('web' or 'app')"
            },
            {
                "type": "CLIENT_API_KEY",
                "header": "X-Aegis-Client-Key",
                "description": "Application client authorization key"
            },
            {
                "type": "BEARER_JWT",
                "header": "Authorization: Bearer <token>",
                "description": "User / Admin session token acquired via /api/v1/auth/login"
            }
        ],
        endpoints=ENDPOINTS_MANIFEST,
        rate_limits={
            "sliding_window_seconds": 60,
            "requests_per_minute": settings.RATE_LIMIT_PER_MINUTE,
            "strategy": "Sliding window in Redis / In-Memory cache"
        },
        security_features=[
            "Zero Third-Party Provider Credential Exposure",
            "AES-256 Fernet Credential Encryption at Rest",
            "Outbound SSRF Verification (Strict RFC-1918 Block)",
            "Strict Security Response Headers (HSTS, nosniff, DENY)",
            "Dynamic Masking for Secrets in UI and API"
        ]
    )

    return ApiResponse(success=True, data=manifest)
