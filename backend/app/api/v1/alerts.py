"""
AEGIS UNIFIED DATA CORE - Emergency Alerts API
/api/v1/alerts
Official emergency alerts with real-time broadcasting over WebSocket & Redis Streams.
"""
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.database.session import get_db
from backend.app.database.models import AlertRecord, User, ActivityEvent
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.schemas.unified import AlertItemSchema
from backend.app.ingestion.deduplicator import EventDeduplicator
from backend.app.realtime.manager import EventBroker
from backend.app.api.deps import rate_limit_check, get_current_user

router = APIRouter(prefix="/alerts", tags=["Disaster Alerts"])


class AlertCreateRequest(BaseModel):
    headline: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5, max_length=2000)
    instruction: Optional[str] = Field(default="Stay tuned for further advisories.")
    hazard_type: str = Field(default="CYCLONE", description="CYCLONE, FLOOD, EARTHQUAKE, HEATWAVE, WILDFIRE, SEVERE_WEATHER")
    severity: str = Field(default="warning", description="advisory, watch, warning, emergency")
    state_name: str = Field(default="Andhra Pradesh")
    district_name: Optional[str] = Field(default="Visakhapatnam")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    radius_km: Optional[float] = Field(default=50.0, ge=1.0)
    source_agency: Optional[str] = Field(default="IMD")
    valid_hours: Optional[int] = Field(default=24, ge=1, le=168)


class AlertUpdateRequest(BaseModel):
    severity: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None, description="active, monitoring, resolved, cancelled")
    instruction: Optional[str] = Field(default=None)


def _map_alert_to_schema(a: AlertRecord) -> AlertItemSchema:
    return AlertItemSchema(
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
    )


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
        alerts.append(_map_alert_to_schema(a))

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


@router.post("", response_model=ApiResponse[AlertItemSchema])
async def create_official_alert(
    payload: AlertCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    Publishes an official disaster alert and broadcasts ALERT_CREATED in real time.
    """
    now = datetime.now(timezone.utc)
    alert_code = f"IND-{payload.hazard_type.upper()}-{uuid.uuid4().hex[:6].upper()}"
    alert = AlertRecord(
        id=f"alert-{uuid.uuid4().hex[:12]}",
        alert_code=alert_code,
        headline=payload.headline,
        description=payload.description,
        instruction=payload.instruction,
        hazard_type=payload.hazard_type.upper(),
        severity=payload.severity.lower(),
        status="active",
        state_name=payload.state_name,
        district_name=payload.district_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        radius_km=payload.radius_km or 50.0,
        source_agency=payload.source_agency or "IMD",
        bulletin_id=alert_code,
        published_at=now,
        valid_until=now + timedelta(hours=payload.valid_hours or 24),
        provenance_type="official_warning"
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    schema = _map_alert_to_schema(alert)

    # Broadcast real-time ALERT_CREATED event
    await EventBroker.publish_event(
        event_type="ALERT_CREATED",
        data=schema.model_dump(),
        channel="alerts",
        category="ALERT"
    )

    return ApiResponse(
        success=True,
        data=schema,
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="official_warning",
            source_authority="AEGIS Official Alert Dispatcher",
            processing_version="1.0.0"
        )
    )


@router.patch("/{alert_id}", response_model=ApiResponse[AlertItemSchema])
@router.post("/{alert_id}/update", response_model=ApiResponse[AlertItemSchema])
async def update_official_alert(
    alert_id: str,
    payload: AlertUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    Updates an official disaster alert and broadcasts ALERT_UPDATED in real time.
    """
    res = await db.execute(select(AlertRecord).where(AlertRecord.id == alert_id))
    alert = res.scalars().first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")

    if payload.severity is not None:
        alert.severity = payload.severity.lower()
    if payload.status is not None:
        alert.status = payload.status.lower()
    if payload.instruction is not None:
        alert.instruction = payload.instruction

    await db.commit()
    await db.refresh(alert)

    schema = _map_alert_to_schema(alert)

    # Broadcast real-time ALERT_UPDATED event
    await EventBroker.publish_event(
        event_type="ALERT_UPDATED",
        data=schema.model_dump(),
        channel="alerts",
        category="ALERT"
    )

    return ApiResponse(
        success=True,
        data=schema,
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="official_warning",
            source_authority="AEGIS Official Alert Dispatcher",
            processing_version="1.0.0"
        )
    )
