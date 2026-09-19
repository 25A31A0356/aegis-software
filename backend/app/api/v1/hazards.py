"""
AEGIS UNIFIED DATA CORE - Hazards & Nearby Spatial Search API
/api/v1/hazards
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import math
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.database.session import get_db
from backend.app.database.models import NormalizedObservation
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.schemas.unified import UnifiedObservation, GeoLocation
from backend.app.ingestion.deduplicator import EventDeduplicator
from backend.app.api.deps import rate_limit_check

router = APIRouter(prefix="/hazards", tags=["Multi-Hazard Observations"])


class NearbyHazardItem(BaseModel):
    id: str
    type: str  # weather, earthquake, flood, wildfire, cyclone, emergency, lightning, air_quality
    severity: str  # LOW, MODERATE, HIGH, CRITICAL
    title: str
    description: str
    distance_km: float
    bearing_degrees: float
    location: Dict[str, Any]
    measurements: Dict[str, Any]
    timestamp: str
    expires_at: Optional[str] = None
    source: str
    source_id: Optional[str] = None
    confidence: float
    status: str  # ACTIVE, EXPIRED, RESOLVED


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates compass bearing in degrees from point 1 to point 2."""
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)
    d_lon = lon2_r - lon1_r
    y = math.sin(d_lon) * math.cos(lat2_r)
    x = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(d_lon)
    bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
    return round(bearing, 1)


@router.get("", response_model=ApiResponse[List[UnifiedObservation]], dependencies=[Depends(rate_limit_check)])
async def list_hazards(
    category: Optional[str] = Query(default=None, description="Category filter (WEATHER, EARTHQUAKE, FLOOD, CYCLONE, etc.)"),
    severity: Optional[str] = Query(default=None, description="Severity filter (critical, warning, moderate, minor)"),
    lat: Optional[float] = Query(default=None, description="Center latitude"),
    lng: Optional[float] = Query(default=None, description="Center longitude"),
    radius_km: Optional[float] = Query(default=150.0, description="Spatial query radius in kilometers"),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns unified hazard observations with spatial and categorical filtering.
    """
    query = select(NormalizedObservation).order_by(desc(NormalizedObservation.observed_at))

    if category and category.upper() != "ALL":
        query = query.where(NormalizedObservation.hazard_type == category.upper())
    if severity and severity.lower() != "all":
        query = query.where(NormalizedObservation.severity == severity.lower())

    query = query.limit(limit)
    result = await db.execute(query)
    rows = result.scalars().all()

    items: List[UnifiedObservation] = []
    for r in rows:
        # Spatial filtering if coordinates provided
        if lat is not None and lng is not None:
            dist = EventDeduplicator.haversine_distance_km(lat, lng, r.latitude, r.longitude)
            if dist > (radius_km or 150.0):
                continue

        items.append(UnifiedObservation(
            id=r.id,
            data_source_id=r.data_source_id,
            source_record_id=r.source_record_id,
            hazard_type=r.hazard_type,
            location=GeoLocation(
                latitude=r.latitude,
                longitude=r.longitude,
                city_name=r.location_name,
                state_name=r.state_name,
                district_name=r.district_name
            ),
            observed_at=r.observed_at,
            received_at=r.received_at,
            valid_until=r.valid_until,
            severity=r.severity,
            risk_level=r.risk_level,
            confidence=r.confidence,
            data_type=r.data_type,
            source_authority=r.source_authority,
            processing_version=r.processing_version,
            measurements=r.measurements or {},
            metadata=r.metadata_json or {}
        ))

    return ApiResponse(
        success=True,
        data=items,
        freshness=FreshnessMetadata(status="fresh", age_seconds=10),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="AEGIS Multi-Hazard Monitoring Grid",
            processing_version="1.0.0"
        )
    )


@router.get("/nearby", response_model=ApiResponse[List[NearbyHazardItem]], dependencies=[Depends(rate_limit_check)])
async def get_nearby_hazards(
    lat: float = Query(..., ge=-90.0, le=90.0, description="User latitude"),
    lng: Optional[float] = Query(default=None, ge=-180.0, le=180.0, description="User longitude (lng)"),
    lon: Optional[float] = Query(default=None, ge=-180.0, le=180.0, description="User longitude (lon)"),
    radius_km: float = Query(default=50.0, ge=1.0, le=500.0, description="Search radius in km"),
    hazard_type: Optional[str] = Query(default=None, description="Optional hazard type filter"),
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Dedicated spatial search returning hazards sorted by proximity to coordinates.
    Includes distance in km, compass bearing, and normalized Aegis severity.
    """
    longitude = lng if lng is not None else lon
    if longitude is None:
        raise HTTPException(status_code=422, detail="Missing required longitude coordinate (provide 'lng' or 'lon').")

    query = select(NormalizedObservation).order_by(desc(NormalizedObservation.observed_at)).limit(200)
    if hazard_type and hazard_type.upper() != "ALL":
        query = query.where(NormalizedObservation.hazard_type == hazard_type.upper())

    res = await db.execute(query)
    rows = res.scalars().all()

    nearby: List[NearbyHazardItem] = []
    for r in rows:
        dist = EventDeduplicator.haversine_distance_km(lat, longitude, r.latitude, r.longitude)
        if dist <= radius_km:
            bearing = calculate_bearing(lat, longitude, r.latitude, r.longitude)
            
            # Map severity to standard Aegis model (LOW, MODERATE, HIGH, CRITICAL)
            sev_raw = (r.severity or "moderate").upper()
            sev_mapped = "MODERATE"
            if sev_raw in ["CRITICAL", "EXTREME"]:
                sev_mapped = "CRITICAL"
            elif sev_raw in ["WARNING", "HIGH"]:
                sev_mapped = "HIGH"
            elif sev_raw in ["MINOR", "LOW"]:
                sev_mapped = "LOW"

            # Title & description derivation
            h_type = (r.hazard_type or "HAZARD").lower()
            loc_name = r.location_name or r.state_name or "Regional Grid"
            title = f"{sev_mapped} {r.hazard_type} Activity at {loc_name}"
            hazard_desc = f"Active {h_type} telemetry detected at {loc_name}, {dist:.1f} km from your location."

            nearby.append(NearbyHazardItem(
                id=r.id,
                type=h_type,
                severity=sev_mapped,
                title=title,
                description=hazard_desc,
                distance_km=round(dist, 1),
                bearing_degrees=bearing,
                location={
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "name": loc_name,
                    "district": r.district_name,
                    "state": r.state_name,
                    "country": "India"
                },
                measurements=r.measurements or {},
                timestamp=r.observed_at.isoformat() if r.observed_at else datetime.now(timezone.utc).isoformat(),
                expires_at=r.valid_until.isoformat() if r.valid_until else None,
                source=r.source_authority or "AEGIS Multi-Hazard Grid",
                source_id=r.source_record_id,
                confidence=r.confidence or 1.0,
                status="ACTIVE"
            ))

    # Sort strictly by distance ascending
    nearby.sort(key=lambda x: x.distance_km)
    nearby = nearby[:limit]

    return ApiResponse(
        success=True,
        data=nearby,
        freshness=FreshnessMetadata(status="fresh", age_seconds=5),
        provenance=ProvenanceMetadata(
            data_type="spatial_proximity_query",
            source_authority="AEGIS Multi-Hazard Monitoring Grid",
            processing_version="1.0.0"
        )
    )
