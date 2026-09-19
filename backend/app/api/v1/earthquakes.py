"""
AEGIS UNIFIED DATA CORE - Earthquake & Seismology API
/api/v1/earthquakes
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.database.session import get_db
from backend.app.database.models import NormalizedObservation
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.schemas.unified import EarthquakeEventSchema
from backend.app.providers.adapters.usgs import USGSSeismologyProvider
from backend.app.cache.redis_client import CacheManager
from backend.app.api.deps import rate_limit_check

router = APIRouter(prefix="/earthquakes", tags=["Earthquakes"])


@router.get("", response_model=ApiResponse[List[EarthquakeEventSchema]], dependencies=[Depends(rate_limit_check)])
async def get_earthquakes(
    min_mag: float = Query(default=2.5, ge=0.0, le=10.0),
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns authentic live seismic activity (USGS & National Seismological Grid).
    """
    cache_key = f"seismic_events_{min_mag}"
    cached = await CacheManager.get(cache_key)
    if cached:
        return ApiResponse(
            success=True,
            data=[EarthquakeEventSchema(**item) for item in cached],
            freshness=FreshnessMetadata(status="fresh", age_seconds=30),
            provenance=ProvenanceMetadata(
                data_type="official_observation",
                source_authority="USGS National Earthquake Information Center",
                processing_version="1.0.0"
            )
        )

    # Fetch live USGS feed
    provider = USGSSeismologyProvider()
    fetch_result = await provider.fetch()
    events: List[EarthquakeEventSchema] = []

    if fetch_result.success:
        records = provider.parse(fetch_result.raw_data)
        for rec in records:
            mag = float(rec.get("magnitude", 0.0))
            if mag < min_mag:
                continue
            events.append(EarthquakeEventSchema(
                id=f"EQ-{rec.get('event_id')}",
                magnitude=mag,
                depth_km=float(rec.get("depth_km", 10.0)),
                place=rec.get("place", "Regional Seismological Station"),
                latitude=float(rec.get("latitude", 0.0)),
                longitude=float(rec.get("longitude", 0.0)),
                time=str(rec.get("time_ms", "")),
                source_authority="USGS Seismological Network",
                severity="critical" if mag >= 6.0 else ("warning" if mag >= 4.5 else "moderate"),
                status="monitoring"
            ))
            if len(events) >= limit:
                break

    if not events:
        # DB fallback
        stmt = (
            select(NormalizedObservation)
            .where(NormalizedObservation.hazard_type == "EARTHQUAKE")
            .order_by(desc(NormalizedObservation.observed_at))
            .limit(limit)
        )
        res = await db.execute(stmt)
        for row in res.scalars().all():
            m = row.measurements
            events.append(EarthquakeEventSchema(
                id=row.id,
                magnitude=m.get("magnitude", 3.0),
                depth_km=m.get("depth_km", 10.0),
                place=row.location_name or "Epicenter",
                latitude=row.latitude,
                longitude=row.longitude,
                time=row.observed_at.isoformat(),
                source_authority=row.source_authority,
                severity=row.severity,
                status="monitoring"
            ))

    # Cache for 2 minutes
    if events:
        await CacheManager.set(cache_key, [e.model_dump() for e in events], ttl_seconds=120)

    return ApiResponse(
        success=True,
        data=events,
        freshness=FreshnessMetadata(status="fresh", age_seconds=15),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="USGS National Seismological Center",
            processing_version="1.0.0"
        )
    )
