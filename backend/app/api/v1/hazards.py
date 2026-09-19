"""
AEGIS UNIFIED DATA CORE - Hazards API
/api/v1/hazards
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.database.session import get_db
from backend.app.database.models import NormalizedObservation
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.schemas.unified import UnifiedObservation, GeoLocation
from backend.app.ingestion.deduplicator import EventDeduplicator
from backend.app.api.deps import rate_limit_check

router = APIRouter(prefix="/hazards", tags=["Multi-Hazard Observations"])


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
