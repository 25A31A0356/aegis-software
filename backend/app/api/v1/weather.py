"""
AEGIS UNIFIED DATA CORE - Weather Telemetry API
/api/v1/weather
"""
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.database.session import get_db
from backend.app.database.models import NormalizedObservation
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.schemas.unified import WeatherTelemetryPayload
from backend.app.cache.redis_client import CacheManager
from backend.app.api.deps import rate_limit_check
from backend.app.providers.adapters.open_meteo import OpenMeteoProvider

router = APIRouter(prefix="/weather", tags=["Weather Telemetry"])


@router.get("", response_model=ApiResponse[WeatherTelemetryPayload], dependencies=[Depends(rate_limit_check)])
async def get_weather(
    lat: float = Query(default=19.0760, ge=-90.0, le=90.0, description="Latitude"),
    lng: float = Query(default=72.8777, ge=-180.0, le=180.0, description="Longitude"),
    city: Optional[str] = Query(default=None, description="City name"),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns normalized real-time weather telemetry for coordinates.
    Retrieves from Redis hot cache or queries live provider adapter.
    """
    cache_key = f"weather_{lat:.2f}_{lng:.2f}"
    cached = await CacheManager.get(cache_key)
    if cached:
        return ApiResponse(
            success=True,
            data=WeatherTelemetryPayload(**cached),
            freshness=FreshnessMetadata(status="fresh", age_seconds=15),
            provenance=ProvenanceMetadata(
                data_type="official_observation",
                source_authority="Open-Meteo & IMD Telemetry Network",
                processing_version="1.0.0"
            )
        )

    # Fetch live using OpenMeteoProvider
    provider = OpenMeteoProvider()
    fetch_result = await provider.fetch(custom_params={"latitude": lat, "longitude": lng})
    
    if not fetch_result.success:
        # Check database for historical fallback
        stmt = (
            select(NormalizedObservation)
            .where(NormalizedObservation.hazard_type == "WEATHER")
            .order_by(desc(NormalizedObservation.observed_at))
            .limit(1)
        )
        res = await db.execute(stmt)
        latest_obs = res.scalars().first()
        if latest_obs:
            m = latest_obs.measurements
            payload = WeatherTelemetryPayload(
                city_name=city or latest_obs.location_name or "Regional Station",
                state_name=latest_obs.state_name or "India",
                coordinates=[latest_obs.latitude, latest_obs.longitude],
                observed_at=latest_obs.observed_at.isoformat(),
                condition="Scattered cloud cover with regional breeze",
                condition_code="partly_cloudy",
                temperature=m.get("temperature_c", 28.0),
                feels_like=m.get("apparent_temperature_c", 30.0),
                humidity=m.get("humidity_percent", 65.0),
                wind_speed=m.get("wind_speed_kmh", 14.0),
                wind_direction="SW",
                rain_probability=20.0,
                rainfall_expected_mm=m.get("precipitation_mm", 0.0),
                uv_index=m.get("uv_index", 5.0),
                barometric_pressure_hpa=m.get("pressure_hpa", 1012.0),
                visibility_km=8.0,
                air_quality_index=65.0,
                air_quality_status="Moderate",
                source=latest_obs.source_authority,
                provenance_type="cached",
                freshness_status="stale"
            )
            return ApiResponse(
                success=True,
                data=payload,
                freshness=FreshnessMetadata(status="stale", age_seconds=300),
                provenance=ProvenanceMetadata(
                    data_type="cached",
                    source_authority=latest_obs.source_authority,
                    processing_version="1.0.0"
                )
            )
        raise HTTPException(status_code=503, detail="Live meteorological telemetry currently unavailable.")

    parsed = provider.parse(fetch_result.raw_data)
    if not parsed:
        raise HTTPException(status_code=502, detail="Unable to parse meteorological provider response.")

    norm = provider.normalize(parsed[0])
    m = norm.measurements
    temp = m.get("temperature_c", 30.0)
    wind = m.get("wind_speed_kmh", 12.0)
    precip = m.get("precipitation_mm", 0.0)

    # Condition string derived from metrics
    condition = "Clear Skies & Sunny"
    condition_code = "sunny"
    if precip >= 15.0 or wind >= 45.0:
        condition = "Thunderstorms & Heavy Inundation Rain"
        condition_code = "thunderstorm"
    elif precip > 0.0:
        condition = "Passing Rain Showers"
        condition_code = "rain"
    elif temp >= 40.0:
        condition = "Extreme Heatwave Warning"
        condition_code = "heatwave"

    data_payload = {
        "city_name": city or "Local Station",
        "state_name": "Maharashtra",
        "coordinates": [lat, lng],
        "observed_at": norm.observed_at.isoformat(),
        "condition": condition,
        "condition_code": condition_code,
        "temperature": temp,
        "feels_like": m.get("apparent_temperature_c", temp + 2),
        "humidity": m.get("humidity_percent", 65.0),
        "wind_speed": wind,
        "wind_direction": "SW",
        "rain_probability": 75.0 if precip > 0 else 15.0,
        "rainfall_expected_mm": precip,
        "uv_index": float(m.get("uv_index", 6.0)),
        "barometric_pressure_hpa": float(m.get("pressure_hpa", 1012.0)),
        "visibility_km": 8.0,
        "air_quality_index": 68.0,
        "air_quality_status": "Moderate",
        "source": "Open-Meteo & IMD Telemetry Network",
        "provenance_type": "official_observation",
        "freshness_status": "fresh"
    }

    # Cache in Redis
    await CacheManager.set(cache_key, data_payload, ttl_seconds=300)

    return ApiResponse(
        success=True,
        data=WeatherTelemetryPayload(**data_payload),
        freshness=FreshnessMetadata(status="fresh", age_seconds=5),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="Open-Meteo & IMD Telemetry Network",
            processing_version="1.0.0"
        )
    )
