"""
AEGIS UNIFIED DATA CORE - Mobile Client Optimization API
/api/v1/mobile
Lightweight endpoints specifically tailored for https://github.com/25A31A0356/aegis-alert (Android & iOS)
"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.database.session import get_db
from backend.app.database.models import AlertRecord, NormalizedObservation
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.ingestion.deduplicator import EventDeduplicator
from backend.app.api.deps import rate_limit_check

router = APIRouter(prefix="/mobile", tags=["Mobile App Client Sync"])


class MobileSyncBundle(BaseModel):
    nearby_alerts_count: int
    threat_level: str
    active_alerts: List[Dict[str, Any]]
    nearby_hazards: List[Dict[str, Any]]
    emergency_helplines: Dict[str, str]
    offline_sync_version: str


@router.get("/sync", response_model=ApiResponse[MobileSyncBundle], dependencies=[Depends(rate_limit_check)])
async def get_mobile_sync_bundle(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    radius_km: float = Query(default=50.0, ge=1.0, le=500.0),
    db: AsyncSession = Depends(get_db)
):
    """
    Single-call low-bandwidth payload for mobile devices containing nearby alerts, local hazards, and emergency contacts.
    """
    # Fetch active alerts
    alert_query = select(AlertRecord).where(AlertRecord.status.in_(["active", "monitoring"])).order_by(desc(AlertRecord.published_at)).limit(20)
    alert_res = await db.execute(alert_query)
    alert_rows = alert_res.scalars().all()

    filtered_alerts = []
    max_severity = "LOW"

    for a in alert_rows:
        dist = EventDeduplicator.haversine_distance_km(lat, lon, a.latitude, a.longitude)
        if dist <= radius_km:
            if a.severity.upper() == "CRITICAL":
                max_severity = "EXTREME"
            elif a.severity.upper() == "WARNING" and max_severity != "EXTREME":
                max_severity = "HIGH"

            filtered_alerts.append({
                "id": a.id,
                "code": a.alert_code,
                "headline": a.headline,
                "hazard_type": a.hazard_type,
                "severity": a.severity,
                "instruction": a.instruction,
                "distance_km": round(dist, 1),
                "published_at": a.published_at.isoformat() if a.published_at else "",
            })

    # Fetch recent normalized observations within radius
    obs_query = select(NormalizedObservation).order_by(desc(NormalizedObservation.observed_at)).limit(30)
    obs_res = await db.execute(obs_query)
    obs_rows = obs_res.scalars().all()

    filtered_obs = []
    for o in obs_rows:
        dist = EventDeduplicator.haversine_distance_km(lat, lon, o.latitude, o.longitude)
        if dist <= radius_km:
            filtered_obs.append({
                "id": o.id,
                "hazard_type": o.hazard_type,
                "location_name": o.location_name,
                "distance_km": round(dist, 1),
                "severity": o.severity,
                "measurements": o.measurements,
                "observed_at": o.observed_at.isoformat() if o.observed_at else "",
            })

    helplines = {
        "National Emergency Number": "112",
        "NDRF Disaster Response": "011-24363260 / 1078",
        "Disaster Management Services": "108",
        "Ambulance Services": "102",
        "Fire Brigade": "101",
        "Police Emergency": "100",
        "Women Safety Helpline": "1091",
        "Child Safety Helpline": "1098",
    }

    bundle = MobileSyncBundle(
        nearby_alerts_count=len(filtered_alerts),
        threat_level=max_severity,
        active_alerts=filtered_alerts,
        nearby_hazards=filtered_obs,
        emergency_helplines=helplines,
        offline_sync_version="1.0.0"
    )

    return ApiResponse(
        success=True,
        data=bundle,
        freshness=FreshnessMetadata(status="fresh", age_seconds=5),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="AEGIS Unified Mobile Gateway",
            processing_version="1.0.0"
        )
    )
