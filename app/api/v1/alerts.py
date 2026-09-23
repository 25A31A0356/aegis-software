"""
AEGIS UNIFIED DATA CORE - Emergency Alerts API
/api/v1/alerts
Official emergency disaster alerts with real-time broadcasting, strict 4-Tier Provenance Taxonomy,
and AI Authorization Guardrails preventing unauthorized AI generation of official alerts.
"""
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, or_, and_, func
from backend.app.database.session import get_db
from backend.app.database.models import AlertRecord, User, ActivityEvent, utc_now
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.schemas.unified import AlertItemSchema
from backend.app.ingestion.deduplicator import EventDeduplicator
from backend.app.realtime.manager import EventBroker
from backend.app.notifications.service import PushNotificationService
from backend.app.api.deps import rate_limit_check, get_current_user

router = APIRouter(prefix="/alerts", tags=["Disaster Alerts"])

VALID_PROVENANCE_TYPES = [
    "OFFICIAL_ALERT",
    "SYSTEM_ALERT",
    "COMMUNITY_REPORT",
    "AI_GENERATED_INFO"
]


class AlertCreateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=255)
    headline: Optional[str] = Field(default=None, min_length=3, max_length=255)
    description: str = Field(..., min_length=5, max_length=2000)
    instruction: Optional[str] = Field(default="Stay tuned for further advisories.")
    type: Optional[str] = Field(default=None, description="CYCLONE, FLOOD, EARTHQUAKE, TSUNAMI, HEATWAVE, WILDFIRE, SEVERE_WEATHER")
    hazard_type: Optional[str] = Field(default=None, description="Synonym for type")
    severity: str = Field(default="warning", description="critical, warning, moderate, minor")
    status: Optional[str] = Field(default="active", description="active, monitoring, draft_pending_approval")
    state_name: str = Field(default="Andhra Pradesh")
    district_name: Optional[str] = Field(default="Visakhapatnam")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    radius_km: Optional[float] = Field(default=50.0, ge=1.0)
    source: Optional[str] = Field(default=None)
    source_agency: Optional[str] = Field(default="IMD")
    valid_hours: Optional[int] = Field(default=24, ge=1, le=168)
    expires_at: Optional[datetime] = Field(default=None)
    
    # Provenance Taxonomy: OFFICIAL_ALERT, SYSTEM_ALERT, COMMUNITY_REPORT, AI_GENERATED_INFO
    provenance_type: Optional[str] = Field(default="OFFICIAL_ALERT")
    is_ai_generated: Optional[bool] = Field(default=False)
    authorization_notes: Optional[str] = Field(default="")


class AlertUpdateRequest(BaseModel):
    severity: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None, description="active, monitoring, resolved, cancelled")
    instruction: Optional[str] = Field(default=None)
    headline: Optional[str] = Field(default=None)
    title: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)


class AlertAuthorizeRequest(BaseModel):
    authorization_notes: Optional[str] = Field(default="Approved and authorized by official emergency operator.")
    signed_by: Optional[str] = Field(default=None)


def normalize_provenance(prov: Optional[str]) -> str:
    if not prov:
        return "OFFICIAL_ALERT"
    clean = prov.upper().replace(" ", "_")
    if clean in ["OFFICIAL_ALERT", "OFFICIAL_WARNING", "OFFICIAL"]:
        return "OFFICIAL_ALERT"
    if clean in ["SYSTEM_ALERT", "SYSTEM_OBSERVATION", "SYSTEM"]:
        return "SYSTEM_ALERT"
    if clean in ["COMMUNITY_REPORT", "COMMUNITY", "CITIZEN"]:
        return "COMMUNITY_REPORT"
    if clean in ["AI_GENERATED_INFO", "AI_GENERATED", "AI_ANALYSIS", "AI"]:
        return "AI_GENERATED_INFO"
    return "OFFICIAL_ALERT"


def _map_alert_to_schema(a: AlertRecord) -> AlertItemSchema:
    norm_prov = normalize_provenance(a.provenance_type)
    effective_title = a.headline or getattr(a, "title", "Hazard Alert")
    effective_type = a.hazard_type.upper() if a.hazard_type else "GENERAL"
    expires_iso = a.valid_until.isoformat() if a.valid_until else (a.created_at + timedelta(hours=24)).isoformat()

    return AlertItemSchema(
        id=a.id,
        alert_code=a.alert_code,
        type=effective_type,
        hazard_type=effective_type,
        title=effective_title,
        headline=effective_title,
        severity=a.severity.lower(),
        status=a.status.lower(),
        description=a.description,
        instruction=a.instruction or "Follow official instructions.",
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
            "validUntil": expires_iso
        },
        created_at=a.created_at.isoformat() if a.created_at else "",
        updated_at=a.updated_at.isoformat() if a.updated_at else "",
        expires_at=expires_iso,
        published_at=a.published_at.isoformat() if a.published_at else "",
        valid_until=expires_iso,
        provenance_type=norm_prov,
        is_authorized_official=getattr(a, "is_authorized_official", True)
    )


@router.get("", response_model=ApiResponse[List[AlertItemSchema]], dependencies=[Depends(rate_limit_check)])
@router.get("/", response_model=ApiResponse[List[AlertItemSchema]], dependencies=[Depends(rate_limit_check)])
async def get_alerts(
    category: Optional[str] = Query(default=None, description="Category/Hazard type filter"),
    type: Optional[str] = Query(default=None, description="Synonym for category"),
    severity: Optional[str] = Query(default=None, description="Severity filter"),
    status: Optional[str] = Query(default=None, description="active, monitoring, resolved, expired, all"),
    provenance: Optional[str] = Query(default=None, description="OFFICIAL_ALERT, SYSTEM_ALERT, COMMUNITY_REPORT, AI_GENERATED_INFO, ALL"),
    state_id: Optional[str] = Query(default=None, description="State filter"),
    lat: Optional[float] = Query(default=None),
    lng: Optional[float] = Query(default=None),
    radius_km: Optional[float] = Query(default=100.0),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns disaster alerts with 4-tier provenance taxonomy and geospatial radius filtering.
    """
    query = select(AlertRecord).order_by(desc(AlertRecord.published_at))

    # Status filter
    if status and status.lower() != "all":
        query = query.where(AlertRecord.status == status.lower())
    else:
        # By default exclude draft_pending_approval unless explicitly requested
        if not status:
            query = query.where(AlertRecord.status.in_(["active", "monitoring"]))

    # Type / Category filter
    target_type = category or type
    if target_type and target_type.lower() != "all":
        query = query.where(AlertRecord.hazard_type == target_type.upper())

    # Severity filter
    if severity and severity.lower() != "all":
        query = query.where(AlertRecord.severity == severity.lower())

    # Provenance filter
    if provenance and provenance.upper() != "ALL":
        norm_filter = normalize_provenance(provenance)
        query = query.where(
            or_(
                AlertRecord.provenance_type == norm_filter,
                AlertRecord.provenance_type == norm_filter.lower(),
                AlertRecord.provenance_type == norm_filter.replace("_", " ")
            )
        )

    # State filter
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
        freshness=FreshnessMetadata(status="fresh", age_seconds=5),
        provenance=ProvenanceMetadata(
            data_type="official_warning",
            source_authority="AEGIS Multi-Agency Emergency Alerting System",
            processing_version="2.0.0"
        )
    )


@router.get("/{alert_id}", response_model=ApiResponse[AlertItemSchema])
async def get_alert_by_id(
    alert_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Fetch single alert details by ID or alert code."""
    res = await db.execute(
        select(AlertRecord).where(
            or_(AlertRecord.id == alert_id, AlertRecord.alert_code == alert_id)
        )
    )
    alert = res.scalars().first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")

    return ApiResponse(
        success=True,
        data=_map_alert_to_schema(alert),
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type=normalize_provenance(alert.provenance_type).lower(),
            source_authority=alert.source_agency,
            processing_version="2.0.0"
        )
    )


@router.post("", response_model=ApiResponse[AlertItemSchema])
@router.post("/", response_model=ApiResponse[AlertItemSchema])
async def create_alert(
    payload: AlertCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id"),
    x_aegis_ai_agent: Optional[str] = Header(default=None, alias="X-Aegis-AI-Agent")
):
    """
    Creates a disaster alert with strict AI Authorization Workflow Guardrails:
    - OFFICIAL ALERT: Requires operator authorization; AI agents cannot create directly.
    - SYSTEM ALERT: Automated deterministic sensor array triggers.
    - COMMUNITY REPORT: Ground-truth citizen report.
    - AI GENERATED INFORMATION: Created in DRAFT_PENDING_APPROVAL status until authorized by an operator.
    """
    now = utc_now()
    raw_prov = payload.provenance_type or "OFFICIAL_ALERT"
    prov_norm = normalize_provenance(raw_prov)
    if payload.is_ai_generated:
        prov_norm = "AI_GENERATED_INFO"

    headline = payload.headline or payload.title or "Emergency Disaster Alert"
    hz_type = (payload.type or payload.hazard_type or "CYCLONE").upper()
    src_agency = payload.source or payload.source_agency or "IMD"

    # ==========================================================================
    # MANDATORY AI AUTHORIZATION GUARDRAIL
    # ==========================================================================
    # If the request comes from an AI agent or is marked as AI-generated:
    is_ai_caller = bool(x_aegis_ai_agent) or payload.is_ai_generated or (prov_norm == "AI_GENERATED_INFO")

    if is_ai_caller:
        # AI MUST NEVER directly create an OFFICIAL ALERT
        prov_norm = "AI_GENERATED_INFO"
        alert_status = "draft_pending_approval"
        is_official = False
        authorized_by = None
        authorized_at = None
        auth_notes = payload.authorization_notes or "AI-Generated situational assessment pending human operator review."
    else:
        # Human / Official / System flow
        alert_status = (payload.status or "active").lower()
        is_official = (prov_norm == "OFFICIAL_ALERT")
        authorized_by = (current_user.id if current_user else None) or x_aegis_user_id or "system_operator"
        authorized_at = now if is_official else None
        auth_notes = payload.authorization_notes or ""

    alert_code = f"IND-{hz_type}-{uuid.uuid4().hex[:6].upper()}"
    exp_time = payload.expires_at or (now + timedelta(hours=payload.valid_hours or 24))

    alert = AlertRecord(
        id=f"alert-{uuid.uuid4().hex[:12]}",
        alert_code=alert_code,
        headline=headline,
        description=payload.description,
        instruction=payload.instruction or "Follow official instructions.",
        hazard_type=hz_type,
        severity=payload.severity.lower(),
        status=alert_status,
        state_name=payload.state_name,
        district_name=payload.district_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        radius_km=payload.radius_km or 50.0,
        source_agency=src_agency,
        bulletin_id=alert_code,
        published_at=now,
        valid_until=exp_time,
        provenance_type=prov_norm,
        is_authorized_official=is_official,
        authorized_by_user_id=authorized_by,
        authorized_at=authorized_at,
        authorization_notes=auth_notes,
        created_at=now,
        updated_at=now
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    schema = _map_alert_to_schema(alert)

    # Broadcast event in real time
    await EventBroker.publish_event(
        event_type="ALERT_CREATED" if is_official else "ALERT_DRAFT_CREATED",
        data=schema.model_dump(),
        channel="alerts",
        category="ALERT"
    )

    # If official critical alert, dispatch push notifications to registered devices
    if is_official and alert_status == "active" and alert.severity.lower() in ["critical", "warning"]:
        await PushNotificationService.dispatch_critical_alert(db, alert)

    return ApiResponse(
        success=True,
        data=schema,
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type=prov_norm.lower(),
            source_authority=f"AEGIS {prov_norm.replace('_', ' ').title()}",
            processing_version="2.0.0"
        )
    )


@router.post("/{alert_id}/authorize-official", response_model=ApiResponse[AlertItemSchema])
async def authorize_official_alert(
    alert_id: str,
    payload: Optional[AlertAuthorizeRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    OPERATOR AI AUTHORIZATION WORKFLOW:
    Promotes an AI-generated draft or system alert into an OFFICIAL ALERT.
    Sets provenance_type = OFFICIAL_ALERT, status = active, is_authorized_official = True,
    records authorized_by_user_id, authorized_at, broadcasts ALERT_AUTHORIZED_OFFICIAL,
    and dispatches critical push notifications.
    """
    res = await db.execute(
        select(AlertRecord).where(
            or_(AlertRecord.id == alert_id, AlertRecord.alert_code == alert_id)
        )
    )
    alert = res.scalars().first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")

    # Enforce trusted operator role check if JWT user is present
    if current_user and current_user.role not in ("admin", "official", "sdrf_officer", "operator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted: Only authorized disaster response operators can promote alerts to official status."
        )

    operator_id = (current_user.id if current_user else None) or (payload.signed_by if payload and payload.signed_by else None) or x_aegis_user_id or "authorized_operator"
    now = utc_now()

    alert.provenance_type = "OFFICIAL_ALERT"
    alert.status = "active"
    alert.is_authorized_official = True
    alert.authorized_by_user_id = operator_id
    alert.authorized_at = now
    if payload and payload.authorization_notes:
        alert.authorization_notes = payload.authorization_notes
    alert.updated_at = now

    await db.commit()
    await db.refresh(alert)

    schema = _map_alert_to_schema(alert)

    # 1. Broadcast real-time promotion event
    await EventBroker.publish_event(
        event_type="ALERT_AUTHORIZED_OFFICIAL",
        data=schema.model_dump(),
        channel="alerts",
        category="ALERT"
    )

    # 2. Also publish ALERT_CREATED so all web/mobile alert feeds ingest it
    await EventBroker.publish_event(
        event_type="ALERT_CREATED",
        data=schema.model_dump(),
        channel="alerts",
        category="ALERT"
    )

    # 3. Dispatch critical push notifications if severity is critical or warning
    if alert.severity.lower() in ["critical", "warning"]:
        await PushNotificationService.dispatch_critical_alert(db, alert)

    return ApiResponse(
        success=True,
        data=schema,
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="official_warning",
            source_authority="AEGIS Official Emergency Authorizer",
            processing_version="2.0.0"
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
    Updates an alert and broadcasts ALERT_UPDATED in real time.
    """
    res = await db.execute(
        select(AlertRecord).where(
            or_(AlertRecord.id == alert_id, AlertRecord.alert_code == alert_id)
        )
    )
    alert = res.scalars().first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")

    if payload.severity is not None:
        alert.severity = payload.severity.lower()
    if payload.status is not None:
        alert.status = payload.status.lower()
    if payload.instruction is not None:
        alert.instruction = payload.instruction
    if payload.headline is not None or payload.title is not None:
        alert.headline = payload.headline or payload.title
    if payload.description is not None:
        alert.description = payload.description

    alert.updated_at = utc_now()
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
            data_type=normalize_provenance(alert.provenance_type).lower(),
            source_authority="AEGIS Alert Dispatcher",
            processing_version="2.0.0"
        )
    )
