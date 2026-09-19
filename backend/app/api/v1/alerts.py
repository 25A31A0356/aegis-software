"""
AEGIS UNIFIED DATA CORE - Emergency Alerts API
/api/v1/alerts
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.database.session import get_db
from backend.app.database.models import AlertRecord
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.schemas.unified import AlertItemSchema
from backend.app.ingestion.deduplicator import EventDeduplicator
from backend.app.api.deps import rate_limit_check

router = APIRouter(prefix="/alerts", tags=["Disaster Alerts"])


@router.get("", response_model=ApiResponse[List[AlertItemSchema]], dependencies=[Depends(rate_limit_check)])
async def get_alerts(
    category: Optional[str] = Query(default=None, description="Category filter"),
    severity: Optional[str] = Query(default=None, description="Severity filter"),
    state_id: Optional[str] = Query(default=None, description="State filter"),
    lat: Optional[float] = Query(default=None),
    lng: Optional[float] = Query(default=None),
    radius_km: Optional[float] = Query(default=100.0),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns official emergency disaster alerts.
    """
    query = select(AlertRecord).where(AlertRecord.status.in_(["active", "monitoring"])).order_by(desc(AlertRecord.published_at))

    if category and category.lower() != "all":
        query = query.where(AlertRecord.hazard_type == category.upper())
    if severity and severity.lower() != "all":
        query = query.where(AlertRecord.severity == severity.lower())
    if state_id and state_id.lower() != "all":
        query = query.where(AlertRecord.state_name.ilike(f"%{state_id}%"))

    res = await db.execute(query)
    rows = res.scalars().all()

    alerts: List[AlertItemSchema] = []
    for a in rows:
        if lat is not None and lng is not None:
            dist = EventDeduplicator.haversine_distance_km(lat, lng, a.latitude, a.longitude)
            if dist > (radius_km or 100.0):
                continue

        alerts.append(AlertItemSchema(
            id=a.id,
            alert_code=a.alert_code,
            title=a.headline,
            hazard_type=a.hazard_type.lower(),
            severity=a.severity,
            status=a.status,
            headline=a.headline,
            description=a.description,
            instruction=a.instruction,
            location={
                "state": a.state_name,
                "district": a.district_name,
                "coordinates": [a.latitude, a.longitude],
                "radiusKm": a.radius_km
            },
            source={
                "agency": a.source_agency,
                "bulletinId": a.bulletin_id or a.alert_code,
                "publishedAt": a.published_at.isoformat() if a.published_at else "",
                "validUntil": a.valid_until.isoformat() if a.valid_until else ""
            },
            published_at=a.published_at.isoformat() if a.published_at else "",
            valid_until=a.valid_until.isoformat() if a.valid_until else None,
            provenance_type=a.provenance_type
        ))

    return ApiResponse(
        success=True,
        data=alerts,
        freshness=FreshnessMetadata(status="fresh", age_seconds=10),
        provenance=ProvenanceMetadata(
            data_type="official_warning",
            source_authority="NDMA, IMD & CWC Emergency Alerting System",
            processing_version="1.0.0"
        )
    )
