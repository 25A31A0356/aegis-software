"""
AEGIS UNIFIED DATA CORE - Multi-Hazard Correlation & Risk Evaluation API
/api/v1/correlation
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.database.session import get_db
from backend.app.database.models import NormalizedObservation
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.schemas.unified import RiskEvaluationResponse, UnifiedObservation, GeoLocation
from backend.app.engines.correlation import CorrelationEngine
from backend.app.ingestion.deduplicator import EventDeduplicator
from backend.app.api.deps import rate_limit_check

router = APIRouter(prefix="/correlation", tags=["Multi-Source Correlation Engine"])


@router.get("/risk", response_model=ApiResponse[RiskEvaluationResponse], dependencies=[Depends(rate_limit_check)])
async def evaluate_location_risk(
    lat: float = Query(default=19.0760, ge=-90.0, le=90.0),
    lng: float = Query(default=72.8777, ge=-180.0, le=180.0),
    radius_km: float = Query(default=100.0, ge=5.0, le=500.0),
    db: AsyncSession = Depends(get_db)
):
    """
    Correlates multi-hazard observations surrounding coordinates and produces composite risk evaluation.
    """
    stmt = (
        select(NormalizedObservation)
        .order_by(desc(NormalizedObservation.observed_at))
        .limit(100)
    )
    res = await db.execute(stmt)
    rows = res.scalars().all()

    observations: list[UnifiedObservation] = []
    for r in rows:
        dist = EventDeduplicator.haversine_distance_km(lat, lng, r.latitude, r.longitude)
        if dist <= radius_km:
            observations.append(UnifiedObservation(
                id=r.id,
                hazard_type=r.hazard_type,
                location=GeoLocation(latitude=r.latitude, longitude=r.longitude, city_name=r.location_name),
                observed_at=r.observed_at,
                received_at=r.received_at,
                severity=r.severity,
                risk_level=r.risk_level,
                confidence=r.confidence,
                data_type=r.data_type,
                source_authority=r.source_authority,
                measurements=r.measurements or {},
                metadata=r.metadata_json or {}
            ))

    risk_eval = CorrelationEngine.correlate_hazards_for_location(lat, lng, observations, radius_km=radius_km)

    return ApiResponse(
        success=True,
        data=risk_eval,
        freshness=FreshnessMetadata(status="fresh", age_seconds=5),
        provenance=ProvenanceMetadata(
            data_type="derived",
            source_authority="AEGIS Multi-Source Spatial Correlation Engine",
            processing_version="1.0.0"
        )
    )
