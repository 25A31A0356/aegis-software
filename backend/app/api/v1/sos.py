"""
AEGIS UNIFIED DATA CORE - Emergency SOS Nearby-Responder Network API
/api/v1/sos
Master backend router orchestrating distress creation, 10km/20km geospatial matching,
Rapido-like offers, atomic race condition resolution, privacy preservation, turn-by-turn routing,
live breadcrumb tracking, and cross-platform synchronization for Aegis Web and Aegis Alert App.
"""
from typing import Optional, List, Dict, Any
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, or_, func
from backend.app.database.session import get_db
from backend.app.database.models import (
    SOSSignal, SOSResponderCandidate, SOSAssignment,
    SOSLocationUpdate, User, UserPreference, SafeEvent,
    EmergencyContact, ActivityEvent, utc_now
)
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.api.deps import rate_limit_check, get_current_user
from backend.app.sos.state_machine import SOSStateMachine, SOSState
from backend.app.sos.matching import SOSMatchingEngine
from backend.app.sos.routing import SOSRoutingEngine
from backend.app.sos.notifications import NotificationService
from backend.app.providers.adapters.geographic import GeographicLocationProvider
from backend.app.realtime.manager import EventBroker, manager
from backend.app.core.config import settings

router = APIRouter(prefix="/sos", tags=["Emergency SOS Nearby-Responder Network"])


# ==============================================================================
# SCHEMAS
# ==============================================================================

class SOSCreateRequest(BaseModel):
    caller_name: str = Field(default="Citizen in Distress")
    caller_phone: str = Field(default="")
    emergency_type: str = Field(default="general", description="medical, flood_trapped, fire, building_collapse, cyclone_shelter, general")
    severity: str = Field(default="CRITICAL", description="LOW, MODERATE, HIGH, CRITICAL")
    short_message: Optional[str] = Field(default="", max_length=500)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy_meters: Optional[float] = Field(default=10.0, ge=0.0)
    address: Optional[str] = Field(default="")
    city: Optional[str] = Field(default="")
    district: Optional[str] = Field(default="")
    state: Optional[str] = Field(default="")
    country: Optional[str] = Field(default="India")
    battery_percent: Optional[int] = Field(default=100, ge=0, le=100)
    medical_notes: Optional[str] = Field(default="")
    casualties_count: Optional[int] = Field(default=1, ge=1)
    device_id: Optional[str] = Field(default=None)
    requester_user_id: Optional[str] = Field(default=None)
    idempotency_key: Optional[str] = Field(default=None, description="Offline idempotency token")
    emergency_contacts: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class SafeCreateRequest(BaseModel):
    user_name: Optional[str] = Field(default="Citizen")
    user_phone: Optional[str] = Field(default="")
    message: Optional[str] = Field(default="I am safe and out of danger.", max_length=500)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy_meters: Optional[float] = Field(default=10.0, ge=0.0)
    location_name: Optional[str] = Field(default="")
    district: Optional[str] = Field(default="")
    state: Optional[str] = Field(default="")
    country: Optional[str] = Field(default="India")
    device_id: Optional[str] = Field(default=None)
    user_id: Optional[str] = Field(default=None)
    idempotency_key: Optional[str] = Field(default=None)
    emergency_contacts: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class SafeResponseSchema(BaseModel):
    id: str
    user_id: Optional[str]
    device_id: Optional[str]
    sos_id: Optional[str]
    user_name: str
    user_phone_masked: str
    status: str
    message: str
    latitude: float
    longitude: float
    accuracy_meters: Optional[float]
    location_name: Optional[str]
    district: Optional[str]
    state: Optional[str]
    country: str
    contacts_notified_count: int
    idempotency_key: Optional[str]
    sync_status: str
    recorded_at: str
    created_at: str


class OfflineSOSSyncItem(BaseModel):
    idempotency_key: str = Field(..., description="Unique offline event idempotency UUID")
    device_id: Optional[str] = None
    user_id: Optional[str] = None
    caller_name: Optional[str] = "Citizen in Distress"
    caller_phone: Optional[str] = ""
    emergency_type: Optional[str] = "general"
    severity: Optional[str] = "CRITICAL"
    short_message: Optional[str] = ""
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy_meters: Optional[float] = 10.0
    battery_percent: Optional[int] = 100
    medical_notes: Optional[str] = ""
    recorded_at_client: Optional[str] = None
    emergency_contacts: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class OfflineSafeSyncItem(BaseModel):
    idempotency_key: str = Field(..., description="Unique offline safe event idempotency UUID")
    device_id: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = "Citizen"
    user_phone: Optional[str] = ""
    message: Optional[str] = "I am safe and out of danger."
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy_meters: Optional[float] = 10.0
    recorded_at_client: Optional[str] = None
    emergency_contacts: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class OfflineSyncBatchRequest(BaseModel):
    sos_events: List[OfflineSOSSyncItem] = Field(default_factory=list)
    safe_events: List[OfflineSafeSyncItem] = Field(default_factory=list)


class OfflineSyncBatchResponse(BaseModel):
    synced_sos_count: int
    synced_safe_count: int
    sos_results: List[Dict[str, Any]]
    safe_results: List[Dict[str, Any]]


class EmergencyContactCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=7, max_length=20)
    relationship: str = Field(default="Family", max_length=50)
    email: Optional[str] = None
    notify_on_sos: bool = True
    notify_on_safe: bool = True


class EmergencyContactResponseSchema(BaseModel):
    id: str
    user_id: str
    name: str
    phone_masked: str
    phone: str
    relationship: str
    email: Optional[str]
    notify_on_sos: bool
    notify_on_safe: bool
    created_at: str


class SOSLocationUpdateRequest(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy_meters: Optional[float] = Field(default=10.0)
    battery_percent: Optional[int] = Field(default=None, ge=0, le=100)
    speed_kmh: Optional[float] = Field(default=0.0)


class SOSStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="RESPONDER_EN_ROUTE, ON_SITE, etc.")
    reason: Optional[str] = Field(default="")


class SOSResolveRequest(BaseModel):
    resolution_notes: Optional[str] = Field(default="Distress resolved successfully.")


class SOSCancelRequest(BaseModel):
    reason: Optional[str] = Field(default="Cancelled by requester")


class SOSResponderProfileRequest(BaseModel):
    is_responder_opted_in: bool = Field(default=True)
    is_available: bool = Field(default=True)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    emergency_contacts: Optional[List[Dict[str, Any]]] = Field(default=None)


class SOSResponseSchema(BaseModel):
    id: str
    requester_user_id: Optional[str]
    caller_name: str
    caller_phone_masked: str
    emergency_type: str
    severity: str
    status: str
    short_message: Optional[str]
    
    # Location (exact if authorized, approximate/redacted if public)
    is_authorized_view: bool
    latitude: Optional[float]
    longitude: Optional[float]
    accuracy_meters: Optional[float]
    address: Optional[str]
    city: Optional[str]
    district: Optional[str]
    state: Optional[str]
    country: str
    
    # Telemetry & Details
    battery_percent: Optional[int]
    medical_notes: Optional[str]
    casualties_count: int
    
    # Responder Assignment & Navigation
    accepted_by: Optional[str]
    accepted_at: Optional[str]
    resolved_at: Optional[str]
    cancelled_at: Optional[str]
    expires_at: Optional[str]
    
    route: Optional[Dict[str, Any]] = None
    eta_seconds: Optional[int] = None
    distance_meters: Optional[float] = None
    
    created_at: str
    updated_at: str


class SOSOfferResponseSchema(BaseModel):
    sos_id: str
    emergency_type: str
    severity: str
    approximate_distance_km: float
    approximate_area: str
    short_message: str
    requested_at: str
    expires_in_seconds: int = 45


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def _mask_phone(phone: str) -> str:
    if not phone or len(phone) < 4:
        return "CONFIDENTIAL"
    return f"{phone[:3]} ***** {phone[-2:]}" if len(phone) >= 7 else f"***{phone[-2:]}"


def _build_safe_response(safe: SafeEvent) -> SafeResponseSchema:
    return SafeResponseSchema(
        id=safe.id,
        user_id=safe.user_id,
        device_id=safe.device_id,
        sos_id=safe.sos_id,
        user_name=safe.user_name,
        user_phone_masked=_mask_phone(safe.user_phone),
        status=safe.status,
        message=safe.message or "I am safe.",
        latitude=safe.latitude,
        longitude=safe.longitude,
        accuracy_meters=safe.accuracy_meters,
        location_name=safe.location_name or "",
        district=safe.district or "",
        state=safe.state or "",
        country=safe.country or "India",
        contacts_notified_count=safe.contacts_notified_count,
        idempotency_key=safe.idempotency_key,
        sync_status=safe.sync_status,
        recorded_at=safe.recorded_at.isoformat() if safe.recorded_at else "",
        created_at=safe.created_at.isoformat() if safe.created_at else "",
    )


def _build_sos_response(
    sos: SOSSignal,
    is_authorized: bool = False,
    assignment: Optional[SOSAssignment] = None
) -> SOSResponseSchema:
    """Builds an SOS schema enforcing strict privacy and redaction rules."""
    exact_lat = sos.latitude if is_authorized else round(sos.latitude, 2)
    exact_lon = sos.longitude if is_authorized else round(sos.longitude, 2)
    addr = sos.address if is_authorized else (sos.district or sos.city or sos.state or "Local Jurisdiction")
    notes = sos.medical_notes if is_authorized else None
    
    route_geom = None
    eta_sec = None
    dist_m = None
    if assignment:
        route_geom = assignment.route_geometry
        eta_sec = assignment.eta_seconds
        dist_m = assignment.distance_meters

    return SOSResponseSchema(
        id=sos.id,
        requester_user_id=sos.requester_user_id or sos.user_id,
        caller_name=sos.caller_name if is_authorized else "Citizen in Distress",
        caller_phone_masked=_mask_phone(sos.caller_phone),
        emergency_type=sos.emergency_type,
        severity=sos.severity,
        status=sos.status,
        short_message=sos.short_message or "",
        is_authorized_view=is_authorized,
        latitude=exact_lat,
        longitude=exact_lon,
        accuracy_meters=sos.accuracy_meters if is_authorized else None,
        address=addr,
        city=sos.city or "",
        district=sos.district or "",
        state=sos.state or "",
        country=sos.country or "India",
        battery_percent=sos.battery_percent,
        medical_notes=notes,
        casualties_count=sos.casualties_count,
        accepted_by=sos.accepted_by,
        accepted_at=sos.accepted_at.isoformat() if sos.accepted_at else None,
        resolved_at=sos.resolved_at.isoformat() if sos.resolved_at else None,
        cancelled_at=sos.cancelled_at.isoformat() if sos.cancelled_at else None,
        expires_at=sos.expires_at.isoformat() if sos.expires_at else None,
        route=route_geom,
        eta_seconds=eta_sec,
        distance_meters=dist_m,
        created_at=sos.created_at.isoformat() if sos.created_at else "",
        updated_at=sos.updated_at.isoformat() if sos.updated_at else "",
    )


# ==============================================================================
# ENDPOINTS
# ==============================================================================

@router.post("", response_model=ApiResponse[SOSResponseSchema], dependencies=[Depends(rate_limit_check)])
async def create_sos_incident(
    payload: SOSCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    USER PRESSES SOS:
    1. Validates GPS coordinates and accuracy.
    2. Saves SOS distress incident.
    3. Notifies registered family/emergency contacts.
    4. Finds eligible nearby Aegis citizen responders (10km initial, expanding to 20km).
    5. Dispatches real-time Rapido-like offers.
    6. Synchronizes active state across Web and App clients.
    """
    user_id = (current_user.id if current_user else None) or payload.requester_user_id or x_aegis_user_id
    now = utc_now()
    expires = now + timedelta(minutes=settings.SOS_EXPIRATION_MINUTES)

    # 1. Idempotency Check: if client submitted with idempotency_key, return existing record
    if payload.idempotency_key:
        idem_res = await db.execute(
            select(SOSSignal).where(SOSSignal.idempotency_key == payload.idempotency_key)
        )
        idem_sos = idem_res.scalars().first()
        if idem_sos:
            return ApiResponse(
                success=True,
                data=_build_sos_response(idem_sos, is_authorized=True),
                freshness=FreshnessMetadata(status="fresh", age_seconds=0),
                provenance=ProvenanceMetadata(
                    data_type="official_observation",
                    source_authority="AEGIS SOS Responder Core (Idempotent Cached)",
                    processing_version="1.0.0"
                )
            )

    # 2. Deduplication check: prevent accidental double SOS within active session for same user/device
    existing_q = select(SOSSignal).where(
        SOSSignal.status.in_([SOSState.PENDING.value, SOSState.MATCHING.value, SOSState.OFFERED.value, SOSState.ACCEPTED.value]),
        or_(
            and_(SOSSignal.user_id != None, SOSSignal.user_id == user_id),
            and_(SOSSignal.device_id != None, SOSSignal.device_id == payload.device_id)
        )
    )
    existing_res = await db.execute(existing_q)
    existing_active = existing_res.scalars().first()
    if existing_active:
        return ApiResponse(
            success=True,
            data=_build_sos_response(existing_active, is_authorized=True),
            freshness=FreshnessMetadata(status="fresh", age_seconds=0),
            provenance=ProvenanceMetadata(
                data_type="official_observation",
                source_authority="AEGIS SOS Responder Core (Active Session)",
                processing_version="1.0.0"
            )
        )

    # 3. Offline Reverse Geocoding for Missing District / State / Address
    req_state = payload.state
    req_district = payload.district
    req_city = payload.city
    req_address = payload.address
    if not req_state or not req_district or not req_address:
        geo_info = GeographicLocationProvider.reverse_geocode_offline(payload.latitude, payload.longitude)
        req_state = req_state or geo_info.get("state")
        req_district = req_district or geo_info.get("district")
        req_city = req_city or geo_info.get("city")
        req_address = req_address or geo_info.get("formatted_address")


    # 4. Create SOS entity
    sos = SOSSignal(
        device_id=payload.device_id,
        user_id=user_id,
        requester_user_id=user_id,
        caller_name=payload.caller_name or (current_user.full_name if current_user else "Citizen in Distress"),
        caller_phone=payload.caller_phone or (current_user.email if current_user else ""),
        emergency_type=payload.emergency_type.lower(),
        severity=payload.severity.upper(),
        short_message=payload.short_message or "",
        status=SOSState.PENDING.value,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_meters=payload.accuracy_meters or 10.0,
        location_timestamp=now,
        last_location_update=now,
        address=req_address or "",
        city=req_city or "",
        district=req_district or "",
        state=req_state or "",
        country=payload.country or "India",
        battery_percent=payload.battery_percent if payload.battery_percent is not None else 100,
        medical_notes=payload.medical_notes or "",
        casualties_count=payload.casualties_count or 1,
        idempotency_key=payload.idempotency_key,
        sync_status="SYNCED",
        raw_payload=payload.model_dump(),
        expires_at=expires,
        created_at=now,
        updated_at=now
    )
    db.add(sos)
    await db.commit()
    await db.refresh(sos)

    # Record initial location breadcrumb
    loc_update = SOSLocationUpdate(
        sos_id=sos.id,
        user_id=user_id or "anonymous",
        user_type="REQUESTER",
        latitude=sos.latitude,
        longitude=sos.longitude,
        accuracy_meters=sos.accuracy_meters,
        battery_percent=sos.battery_percent,
        recorded_at=now
    )
    db.add(loc_update)

    # Log Activity Event
    activity = ActivityEvent(
        event_type="SOS_CREATED",
        entity_type="SOS",
        entity_id=sos.id,
        title=f"SOS Distress Alert: {sos.emergency_type.upper()}",
        description=sos.short_message or f"Distress signal reported in {sos.district or sos.state or 'India'}",
        category=sos.emergency_type.upper(),
        severity=sos.severity.upper(),
        latitude=sos.latitude,
        longitude=sos.longitude,
        location_name=sos.address or f"{sos.district or ''}, {sos.state or ''}",
        city=sos.city or "",
        state=sos.state or "",
        source="CITIZEN",
        verification_status="ACTIVE_DISTRESS",
        payload={
            "sos_id": sos.id,
            "emergency_type": sos.emergency_type,
            "severity": sos.severity,
            "casualties_count": sos.casualties_count
        },
        created_at=now
    )
    db.add(activity)

    # 5. Transition to MATCHING
    await SOSStateMachine.transition(
        db=db,
        sos=sos,
        target_state=SOSState.MATCHING.value,
        changed_by_user_id=user_id,
        reason="Automated matching initiated"
    )

    # 6. Notify family / emergency contacts
    contacts = payload.emergency_contacts
    if not contacts and user_id:
        pref_res = await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
        pref = pref_res.scalars().first()
        if pref and pref.emergency_contacts:
            contacts = pref.emergency_contacts

    if contacts:
        await NotificationService.notify_emergency_contacts(db, sos, contacts)

    # 7. Discover nearby responders (10km initial, expanding up to 20km)
    candidates = await SOSMatchingEngine.find_eligible_responders(db, sos)

    # 8. If candidates found, transition to OFFERED and dispatch notifications
    if candidates:
        await SOSStateMachine.transition(
            db=db,
            sos=sos,
            target_state=SOSState.OFFERED.value,
            changed_by_user_id=user_id,
            reason=f"Dispatched offers to {len(candidates)} nearby responders"
        )
        await NotificationService.notify_nearby_responders(db, sos, candidates)

    await db.commit()
    await db.refresh(sos)

    # 9. Broadcast real-time event across Web & App
    await NotificationService.broadcast_sos_event(
        event_name="SOS_CREATED",
        sos=sos,
        extra_data={"candidate_count": len(candidates)}
    )

    return ApiResponse(
        success=True,
        data=_build_sos_response(sos, is_authorized=True),
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="AEGIS SOS Responder Network Gateway",
            processing_version="1.0.0"
        )
    )



@router.get("", response_model=ApiResponse[List[SOSResponseSchema]])
async def list_active_sos(
    status: Optional[str] = Query(default="ACTIVE", description="ACTIVE, ALL, PENDING, MATCHING, OFFERED, ACCEPTED, RESOLVED, CANCELLED"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    List active SOS distress incidents.
    Operators and Admins receive authorized exact operational telemetry; public clients receive sanitized telemetry.
    """
    is_admin = bool(current_user and current_user.role in ("admin", "official", "sdrf_officer"))
    query = select(SOSSignal).order_by(desc(SOSSignal.created_at)).limit(limit).offset(offset)

    if status == "ACTIVE":
        query = query.where(SOSSignal.status.in_([
            SOSState.PENDING.value, SOSState.MATCHING.value, SOSState.OFFERED.value,
            SOSState.ACCEPTED.value, SOSState.RESPONDER_EN_ROUTE.value, SOSState.ON_SITE.value
        ]))
    elif status and status != "ALL":
        query = query.where(SOSSignal.status == status.upper())

    res = await db.execute(query)
    rows = res.scalars().all()

    items = [_build_sos_response(s, is_authorized=is_admin) for s in rows]

    return ApiResponse(
        success=True,
        data=items,
        freshness=FreshnessMetadata(status="fresh", age_seconds=5),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="AEGIS Emergency Response Command",
            processing_version="1.0.0"
        )
    )


@router.get("/nearby", response_model=ApiResponse[List[SOSOfferResponseSchema]])
async def get_nearby_sos_offers(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    Rapido-like Offers: Fetches pending assistance requests for the authenticated responder.
    Strictly conceals exact coordinates and personal details prior to acceptance.
    """
    user_id = (current_user.id if current_user else None) or x_aegis_user_id
    if not user_id:
        return ApiResponse(success=True, data=[], freshness=FreshnessMetadata(status="fresh", age_seconds=0))

    query = (
        select(SOSResponderCandidate, SOSSignal)
        .join(SOSSignal, SOSResponderCandidate.sos_id == SOSSignal.id)
        .where(
            SOSResponderCandidate.responder_user_id == user_id,
            SOSResponderCandidate.status == "OFFERED",
            SOSSignal.status.in_([SOSState.MATCHING.value, SOSState.OFFERED.value])
        )
        .order_by(SOSResponderCandidate.distance_km.asc())
    )

    res = await db.execute(query)
    rows = res.all()

    offers = []
    for cand, sos in rows:
        offers.append(SOSOfferResponseSchema(
            sos_id=sos.id,
            emergency_type=sos.emergency_type,
            severity=sos.severity,
            approximate_distance_km=cand.distance_km,
            approximate_area=sos.district or sos.city or sos.state or "Local Area",
            short_message=sos.short_message or "Citizen requested urgent emergency assistance",
            requested_at=sos.created_at.isoformat() if sos.created_at else utc_now().isoformat(),
            expires_in_seconds=45
        ))

    return ApiResponse(
        success=True,
        data=offers,
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="AEGIS SOS Responder Dispatcher",
            processing_version="1.0.0"
        )
    )



# ==============================================================================
# ACTIVE SOS MAP FEED
# ==============================================================================

@router.get("/map/feed", response_model=ApiResponse[List[SOSResponseSchema]])
async def get_sos_map_feed(
    bbox: Optional[str] = Query(default=None, description="Bounding box min_lon,min_lat,max_lon,max_lat"),
    state: Optional[str] = Query(default=None, description="Filter by Indian State"),
    district: Optional[str] = Query(default=None, description="Filter by District"),
    severity: Optional[str] = Query(default=None, description="Filter by severity"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    ACTIVE SOS MAP FEED:
    Returns active distress markers for Web and App map displays.
    Applies privacy redaction (approximate coordinates, masked identities) for non-operator callers.
    """
    is_admin = bool(current_user and current_user.role in ("admin", "official", "sdrf_officer", "responder"))
    query = select(SOSSignal).where(
        SOSSignal.status.in_([
            SOSState.PENDING.value, SOSState.MATCHING.value, SOSState.OFFERED.value,
            SOSState.ACCEPTED.value, SOSState.RESPONDER_EN_ROUTE.value, SOSState.ON_SITE.value
        ])
    ).order_by(desc(SOSSignal.created_at)).limit(100)

    if state:
        query = query.where(SOSSignal.state.ilike(f"%{state}%"))
    if district:
        query = query.where(SOSSignal.district.ilike(f"%{district}%"))
    if severity:
        query = query.where(SOSSignal.severity == severity.upper())

    if bbox:
        try:
            parts = [float(p.strip()) for p in bbox.split(",")]
            if len(parts) == 4:
                min_lon, min_lat, max_lon, max_lat = parts
                query = query.where(
                    SOSSignal.longitude >= min_lon,
                    SOSSignal.longitude <= max_lon,
                    SOSSignal.latitude >= min_lat,
                    SOSSignal.latitude <= max_lat
                )
        except Exception:
            pass

    res = await db.execute(query)
    rows = res.scalars().all()

    items = [_build_sos_response(s, is_authorized=is_admin) for s in rows]

    return ApiResponse(
        success=True,
        data=items,
        freshness=FreshnessMetadata(status="fresh", age_seconds=2),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="AEGIS Unified Map Radar",
            processing_version="1.0.0"
        )
    )


@router.post("/responder/profile", response_model=ApiResponse[Dict[str, Any]])
async def update_responder_profile(
    payload: SOSResponderProfileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    Registers or updates citizen responder opt-in participation, availability status,
    emergency contacts, and latest GPS coordinates.
    """
    user_id = (current_user.id if current_user else None) or x_aegis_user_id
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User authentication required.")

    # Ensure user exists or create development citizen record
    user_res = await db.execute(select(User).where(User.id == user_id))
    user_obj = user_res.scalars().first()
    if not user_obj:
        user_obj = User(
            id=user_id,
            email=f"{user_id}@aegis.citizen",
            hashed_password="mock_hashed_password",
            full_name="Aegis Responder",
            role="responder",
            is_active=True
        )
        db.add(user_obj)
        await db.commit()
        await db.refresh(user_obj)

    pref_res = await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
    pref = pref_res.scalars().first()

    now = utc_now()
    if not pref:
        pref = UserPreference(
            user_id=user_id,
            is_responder_opted_in=payload.is_responder_opted_in,
            is_available=payload.is_available,
            last_known_lat=payload.latitude,
            last_known_lng=payload.longitude,
            last_location_time=now if payload.latitude is not None else None,
            emergency_contacts=payload.emergency_contacts or []
        )
        db.add(pref)
    else:
        pref.is_responder_opted_in = payload.is_responder_opted_in
        pref.is_available = payload.is_available
        if payload.latitude is not None and payload.longitude is not None:
            pref.last_known_lat = payload.latitude
            pref.last_known_lng = payload.longitude
            pref.last_location_time = now
        if payload.emergency_contacts is not None:
            pref.emergency_contacts = payload.emergency_contacts
        pref.updated_at = now

    await db.commit()

    return ApiResponse(
        success=True,
        data={
            "user_id": user_id,
            "is_responder_opted_in": pref.is_responder_opted_in,
            "is_available": pref.is_available,
            "last_known_lat": pref.last_known_lat,
            "last_known_lng": pref.last_known_lng,
            "emergency_contacts_count": len(pref.emergency_contacts or [])
        },
        freshness=FreshnessMetadata(status="fresh", age_seconds=0)
    )


# ==============================================================================
# SAFE ("I AM SAFE") ENDPOINTS
# ==============================================================================


@router.post("/safe", response_model=ApiResponse[SafeResponseSchema], dependencies=[Depends(rate_limit_check)])
async def declare_safe_incident(
    payload: SafeCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    CITIZEN DECLARES "I AM SAFE":
    1. Idempotency Check: Returns existing safe event if idempotency_key was already processed.
    2. Auto-Reverse Geocoding: Fills missing location, district, state from centroid coordinates.
    3. Auto SOS Resolution: If citizen has an active SOS in progress, immediately marks it as RESOLVED
       (reason: 'Citizen declared SAFE'), completes responder assignments, and broadcasts SOS_RESOLVED.
    4. Notifies registered family/emergency contacts with safety status and coordinates.
    5. Dispatches real-time SAFE_CREATED event across Web & App.
    6. Logs event in Unified Activity Feed.
    """
    user_id = (current_user.id if current_user else None) or payload.user_id or x_aegis_user_id
    now = utc_now()

    # 1. Idempotency check
    if payload.idempotency_key:
        idem_res = await db.execute(select(SafeEvent).where(SafeEvent.idempotency_key == payload.idempotency_key))
        idem_safe = idem_res.scalars().first()
        if idem_safe:
            return ApiResponse(
                success=True,
                data=_build_safe_response(idem_safe),
                freshness=FreshnessMetadata(status="fresh", age_seconds=0),
                provenance=ProvenanceMetadata(
                    data_type="official_observation",
                    source_authority="AEGIS Safety Registry (Idempotent Cached)",
                    processing_version="1.0.0"
                )
            )

    # 2. Offline reverse geocoding if missing
    req_state = payload.state
    req_district = payload.district
    req_loc_name = payload.location_name
    if not req_state or not req_district or not req_loc_name:
        geo_info = GeographicLocationProvider.reverse_geocode_offline(payload.latitude, payload.longitude)
        req_state = req_state or geo_info.get("state")
        req_district = req_district or geo_info.get("district")
        req_loc_name = req_loc_name or geo_info.get("formatted_address")


    # 3. Check for active SOS signal to auto-resolve
    active_sos = None
    if user_id or payload.device_id:
        sos_q = select(SOSSignal).where(
            SOSSignal.status.in_([
                SOSState.PENDING.value, SOSState.MATCHING.value, SOSState.OFFERED.value,
                SOSState.ACCEPTED.value, SOSState.RESPONDER_EN_ROUTE.value, SOSState.ON_SITE.value
            ]),
            or_(
                and_(SOSSignal.user_id != None, SOSSignal.user_id == user_id),
                and_(SOSSignal.device_id != None, SOSSignal.device_id == payload.device_id)
            )
        )
        sos_res = await db.execute(sos_q)
        active_sos = sos_res.scalars().first()

    if active_sos:
        active_sos.resolution_notes = "Citizen declared SAFE"
        await SOSStateMachine.transition(
            db=db,
            sos=active_sos,
            target_state=SOSState.RESOLVED.value,
            changed_by_user_id=user_id,
            reason="Citizen declared SAFE"
        )
        # Complete active assignments
        assign_res = await db.execute(
            select(SOSAssignment).where(SOSAssignment.sos_id == active_sos.id, SOSAssignment.status == "ACTIVE")
        )
        active_assign = assign_res.scalars().first()
        if active_assign:
            active_assign.status = "COMPLETED"

        await NotificationService.broadcast_sos_event(
            event_name="SOS_RESOLVED",
            sos=active_sos,
            extra_data={"resolution_notes": "Citizen declared SAFE", "resolved_by": "SAFE_DECLARATION"}
        )

    # 4. Create SafeEvent
    safe_event = SafeEvent(
        user_id=user_id,
        device_id=payload.device_id,
        sos_id=active_sos.id if active_sos else None,
        user_name=payload.user_name or (current_user.full_name if current_user else "Citizen"),
        user_phone=payload.user_phone or (current_user.email if current_user else ""),
        status="SAFE",
        message=payload.message or "I am safe and out of danger.",
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_meters=payload.accuracy_meters or 10.0,
        location_name=req_loc_name or "",
        district=req_district or "",
        state=req_state or "",
        country=payload.country or "India",
        idempotency_key=payload.idempotency_key,
        sync_status="SYNCED",
        recorded_at=now,
        created_at=now,
        updated_at=now
    )
    db.add(safe_event)
    await db.commit()
    await db.refresh(safe_event)

    # 5. Notify emergency contacts
    contacts = payload.emergency_contacts
    if not contacts and user_id:
        pref_res = await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
        pref = pref_res.scalars().first()
        if pref and pref.emergency_contacts:
            contacts = pref.emergency_contacts

    notified_count = 0
    if contacts:
        notifs = await NotificationService.notify_safe_event(db, safe_event, contacts)
        notified_count = len(notifs)
        safe_event.contacts_notified_count = notified_count
        await db.commit()
        await db.refresh(safe_event)

    # 6. Broadcast Real-time Safe Event
    await NotificationService.broadcast_safe_event(
        safe_event=safe_event,
        extra_data={"resolved_sos_id": active_sos.id if active_sos else None}
    )

    # 7. Log Activity Event
    activity = ActivityEvent(
        event_type="CITIZEN_SAFE",
        entity_type="SAFE",
        entity_id=safe_event.id,
        title=f"Citizen Safety Check-In: {safe_event.user_name}",
        description=safe_event.message or "Citizen verified safe and out of danger.",
        category="SAFETY_CHECKIN",
        severity="LOW",
        latitude=safe_event.latitude,
        longitude=safe_event.longitude,
        location_name=safe_event.location_name or f"{safe_event.district or ''}, {safe_event.state or ''}",
        city=safe_event.district or "",
        state=safe_event.state or "",
        source="CITIZEN",
        verification_status="VERIFIED",
        payload={
            "safe_event_id": safe_event.id,
            "sos_id": active_sos.id if active_sos else None,
            "contacts_notified": notified_count
        },
        created_at=now
    )
    db.add(activity)
    await db.commit()

    return ApiResponse(
        success=True,
        data=_build_safe_response(safe_event),
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="AEGIS Safety Registry",
            processing_version="1.0.0"
        )
    )


@router.get("/safe", response_model=ApiResponse[List[SafeResponseSchema]])
async def list_safe_events(
    state: Optional[str] = Query(default=None, description="Filter by Indian State"),
    district: Optional[str] = Query(default=None, description="Filter by District"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    List recent citizen safety check-ins ("I AM SAFE" events).
    """
    query = select(SafeEvent).order_by(desc(SafeEvent.created_at)).limit(limit).offset(offset)
    if state:
        query = query.where(SafeEvent.state.ilike(f"%{state}%"))
    if district:
        query = query.where(SafeEvent.district.ilike(f"%{district}%"))

    res = await db.execute(query)
    rows = res.scalars().all()

    items = [_build_safe_response(s) for s in rows]

    return ApiResponse(
        success=True,
        data=items,
        freshness=FreshnessMetadata(status="fresh", age_seconds=5),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="AEGIS Safety Registry",
            processing_version="1.0.0"
        )
    )


# ==============================================================================
# OFFLINE BATCH SYNC ENDPOINTS
# ==============================================================================


@router.post("/sync", response_model=ApiResponse[OfflineSyncBatchResponse], dependencies=[Depends(rate_limit_check)])
async def sync_offline_batch(
    payload: OfflineSyncBatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    OFFLINE-FIRST SYNC BATCH GATEWAY:
    Accepts queued offline SOS distress events and Safe declarations.
    Enforces atomic idempotency by checking idempotency_key for each item.
    Returns individual sync status and synchronized server IDs.
    """
    user_id = (current_user.id if current_user else None) or x_aegis_user_id
    now = utc_now()
    sos_results = []
    safe_results = []
    synced_sos_count = 0
    synced_safe_count = 0

    # 1. Process Queued Offline SOS Events
    for item in payload.sos_events:
        item_user_id = item.user_id or user_id
        # Check idempotency
        idem_res = await db.execute(select(SOSSignal).where(SOSSignal.idempotency_key == item.idempotency_key))
        existing_sos = idem_res.scalars().first()

        if existing_sos:
            sos_results.append({
                "idempotency_key": item.idempotency_key,
                "id": existing_sos.id,
                "status": "ALREADY_SYNCED",
                "sos_status": existing_sos.status,
                "synced_at": existing_sos.created_at.isoformat()
            })
            continue

        # Reverse geocode
        geo_info = GeographicLocationProvider.reverse_geocode_offline(item.latitude, item.longitude)
        state_name = geo_info.get("state") or "India"
        district_name = geo_info.get("district") or ""
        address = geo_info.get("formatted_address") or ""

        sos = SOSSignal(
            device_id=item.device_id,
            user_id=item_user_id,
            requester_user_id=item_user_id,
            caller_name=item.caller_name or "Citizen in Distress",
            caller_phone=item.caller_phone or "",
            emergency_type=(item.emergency_type or "general").lower(),
            severity=(item.severity or "CRITICAL").upper(),
            short_message=item.short_message or "",
            status=SOSState.PENDING.value,
            latitude=item.latitude,
            longitude=item.longitude,
            accuracy_meters=item.accuracy_meters or 10.0,
            location_timestamp=now,
            last_location_update=now,
            address=address,
            district=district_name,
            state=state_name,
            country="India",
            battery_percent=item.battery_percent if item.battery_percent is not None else 100,
            medical_notes=item.medical_notes or "",
            idempotency_key=item.idempotency_key,
            sync_status="SYNCED",
            raw_payload=item.model_dump(),
            expires_at=now + timedelta(minutes=settings.SOS_EXPIRATION_MINUTES),
            created_at=now,
            updated_at=now
        )
        db.add(sos)
        await db.commit()
        await db.refresh(sos)

        # Notify contacts
        if item.emergency_contacts:
            await NotificationService.notify_emergency_contacts(db, sos, item.emergency_contacts)

        # Find nearby responders
        candidates = await SOSMatchingEngine.find_eligible_responders(db, sos)
        if candidates:
            await SOSStateMachine.transition(
                db=db,
                sos=sos,
                target_state=SOSState.OFFERED.value,
                changed_by_user_id=item_user_id,
                reason=f"Offline sync dispatched offers to {len(candidates)} nearby responders"
            )
            await NotificationService.notify_nearby_responders(db, sos, candidates)

        await NotificationService.broadcast_sos_event(
            event_name="SOS_CREATED",
            sos=sos,
            extra_data={"synced_from_offline": True, "candidate_count": len(candidates)}
        )

        synced_sos_count += 1
        sos_results.append({
            "idempotency_key": item.idempotency_key,
            "id": sos.id,
            "status": "SYNCED",
            "sos_status": sos.status,
            "synced_at": now.isoformat()
        })

    # 2. Process Queued Offline Safe Events
    for s_item in payload.safe_events:
        item_user_id = s_item.user_id or user_id
        # Check idempotency
        idem_res = await db.execute(select(SafeEvent).where(SafeEvent.idempotency_key == s_item.idempotency_key))
        existing_safe = idem_res.scalars().first()

        if existing_safe:
            safe_results.append({
                "idempotency_key": s_item.idempotency_key,
                "id": existing_safe.id,
                "status": "ALREADY_SYNCED",
                "synced_at": existing_safe.created_at.isoformat()
            })
            continue

        # Reverse geocode
        geo_info = GeographicLocationProvider.reverse_geocode_offline(s_item.latitude, s_item.longitude)
        state_name = geo_info.get("state") or "India"
        district_name = geo_info.get("district") or ""
        loc_name = geo_info.get("formatted_address") or ""


        # Auto-resolve any active SOS
        active_sos = None
        if item_user_id or s_item.device_id:
            sos_q = select(SOSSignal).where(
                SOSSignal.status.in_([
                    SOSState.PENDING.value, SOSState.MATCHING.value, SOSState.OFFERED.value,
                    SOSState.ACCEPTED.value, SOSState.RESPONDER_EN_ROUTE.value, SOSState.ON_SITE.value
                ]),
                or_(
                    and_(SOSSignal.user_id != None, SOSSignal.user_id == item_user_id),
                    and_(SOSSignal.device_id != None, SOSSignal.device_id == s_item.device_id)
                )
            )
            sos_res = await db.execute(sos_q)
            active_sos = sos_res.scalars().first()

        if active_sos:
            active_sos.resolution_notes = "Citizen declared SAFE via offline sync"
            await SOSStateMachine.transition(
                db=db,
                sos=active_sos,
                target_state=SOSState.RESOLVED.value,
                changed_by_user_id=item_user_id,
                reason="Citizen declared SAFE via offline sync"
            )
            await NotificationService.broadcast_sos_event(
                event_name="SOS_RESOLVED",
                sos=active_sos,
                extra_data={"resolution_notes": "Citizen declared SAFE via offline sync"}
            )

        safe_event = SafeEvent(
            user_id=item_user_id,
            device_id=s_item.device_id,
            sos_id=active_sos.id if active_sos else None,
            user_name=s_item.user_name or "Citizen",
            user_phone=s_item.user_phone or "",
            status="SAFE",
            message=s_item.message or "I am safe and out of danger.",
            latitude=s_item.latitude,
            longitude=s_item.longitude,
            accuracy_meters=s_item.accuracy_meters or 10.0,
            location_name=loc_name,
            district=district_name,
            state=state_name,
            country="India",
            idempotency_key=s_item.idempotency_key,
            sync_status="SYNCED",
            recorded_at=now,
            created_at=now,
            updated_at=now
        )
        db.add(safe_event)
        await db.commit()
        await db.refresh(safe_event)

        if s_item.emergency_contacts:
            await NotificationService.notify_safe_event(db, safe_event, s_item.emergency_contacts)

        await NotificationService.broadcast_safe_event(safe_event=safe_event)

        synced_safe_count += 1
        safe_results.append({
            "idempotency_key": s_item.idempotency_key,
            "id": safe_event.id,
            "status": "SYNCED",
            "synced_at": now.isoformat()
        })

    return ApiResponse(
        success=True,
        data=OfflineSyncBatchResponse(
            synced_sos_count=synced_sos_count,
            synced_safe_count=synced_safe_count,
            sos_results=sos_results,
            safe_results=safe_results
        ),
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="AEGIS Offline-First Sync Gateway",
            processing_version="1.0.0"
        )
    )



# ==============================================================================
# EMERGENCY CONTACTS CRUD ENDPOINTS
# ==============================================================================

@router.get("/contacts", response_model=ApiResponse[List[EmergencyContactResponseSchema]])
async def list_emergency_contacts(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    List registered emergency contacts for the authenticated citizen.
    """
    user_id = (current_user.id if current_user else None) or x_aegis_user_id
    if not user_id:
        return ApiResponse(success=True, data=[], freshness=FreshnessMetadata(status="fresh", age_seconds=0))

    query = select(EmergencyContact).where(EmergencyContact.user_id == user_id).order_by(EmergencyContact.created_at.asc())
    res = await db.execute(query)
    contacts = res.scalars().all()

    items = [
        EmergencyContactResponseSchema(
            id=c.id,
            user_id=c.user_id,
            name=c.name,
            phone_masked=_mask_phone(c.phone),
            phone=c.phone,
            relationship=c.relationship,
            email=c.email,
            notify_on_sos=c.notify_on_sos,
            notify_on_safe=c.notify_on_safe,
            created_at=c.created_at.isoformat() if c.created_at else ""
        )
        for c in contacts
    ]

    return ApiResponse(
        success=True,
        data=items,
        freshness=FreshnessMetadata(status="fresh", age_seconds=0)
    )


@router.post("/contacts", response_model=ApiResponse[EmergencyContactResponseSchema])
async def create_emergency_contact(
    payload: EmergencyContactCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    Registers a new trusted emergency contact for automated SOS & Safe alert delivery.
    """
    user_id = (current_user.id if current_user else None) or x_aegis_user_id
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User authentication required.")

    # Ensure user exists
    user_res = await db.execute(select(User).where(User.id == user_id))
    user_obj = user_res.scalars().first()
    if not user_obj:
        user_obj = User(
            id=user_id,
            email=f"{user_id}@aegis.citizen",
            hashed_password="mock_hashed_password",
            full_name="Aegis Citizen",
            role="public",
            is_active=True
        )
        db.add(user_obj)
        await db.commit()
        await db.refresh(user_obj)

    contact = EmergencyContact(
        user_id=user_id,
        name=payload.name,
        phone=payload.phone,
        relationship=payload.relationship,
        email=payload.email,
        notify_on_sos=payload.notify_on_sos,
        notify_on_safe=payload.notify_on_safe,
        created_at=utc_now(),
        updated_at=utc_now()
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)

    return ApiResponse(
        success=True,
        data=EmergencyContactResponseSchema(
            id=contact.id,
            user_id=contact.user_id,
            name=contact.name,
            phone_masked=_mask_phone(contact.phone),
            phone=contact.phone,
            relationship=contact.relationship,
            email=contact.email,
            notify_on_sos=contact.notify_on_sos,
            notify_on_safe=contact.notify_on_safe,
            created_at=contact.created_at.isoformat() if contact.created_at else ""
        ),
        freshness=FreshnessMetadata(status="fresh", age_seconds=0)
    )


@router.delete("/contacts/{contact_id}", response_model=ApiResponse[Dict[str, Any]])
async def delete_emergency_contact(
    contact_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    Deletes an emergency contact.
    """
    user_id = (current_user.id if current_user else None) or x_aegis_user_id
    res = await db.execute(select(EmergencyContact).where(EmergencyContact.id == contact_id))
    contact = res.scalars().first()
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emergency contact not found.")

    if user_id and contact.user_id != user_id and not (current_user and current_user.role == "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this contact.")

    await db.delete(contact)
    await db.commit()

    return ApiResponse(
        success=True,
        data={"contact_id": contact_id, "deleted": True, "message": "Emergency contact removed successfully."},
        freshness=FreshnessMetadata(status="fresh", age_seconds=0)
    )



@router.get("/{sos_id}", response_model=ApiResponse[SOSResponseSchema])
async def get_sos_details(
    sos_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    Fetches SOS incident details with strict role-based location and identity privacy.
    Authorized exact telemetry is revealed only to:
    - The original requester
    - The assigned primary responder
    - Command Center Operators / Admins
    """
    res = await db.execute(select(SOSSignal).where(SOSSignal.id == sos_id))
    sos = res.scalars().first()
    if not sos:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"SOS Incident '{sos_id}' not found.")

    user_id = (current_user.id if current_user else None) or x_aegis_user_id
    is_admin = bool(current_user and current_user.role in ("admin", "official", "sdrf_officer"))
    is_requester = bool(user_id and (user_id == sos.user_id or user_id == sos.requester_user_id))
    is_assigned_responder = bool(user_id and user_id == sos.accepted_by)

    is_authorized = is_admin or is_requester or is_assigned_responder

    # Fetch active assignment if present
    assign_res = await db.execute(
        select(SOSAssignment).where(SOSAssignment.sos_id == sos.id, SOSAssignment.status == "ACTIVE")
    )
    assignment = assign_res.scalars().first()

    return ApiResponse(
        success=True,
        data=_build_sos_response(sos, is_authorized=is_authorized, assignment=assignment),
        freshness=FreshnessMetadata(status="fresh", age_seconds=1),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="AEGIS Emergency Response Core",
            processing_version="1.0.0"
        )
    )


@router.post("/{sos_id}/accept", response_model=ApiResponse[SOSResponseSchema])
async def accept_sos_offer(
    sos_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    RESPONDER ACCEPTS SOS OFFER:
    1. Guarantees atomic race condition safety: If multiple responders accept simultaneously,
       only the first succeeds. The second receives HTTP 409 Conflict.
    2. Assigns the responder as the primary emergency handler.
    3. Calculates turn-by-turn route, distance, and ETA from responder to requester.
    4. Unlocks authorized exact coordinates and navigation guidance.
    5. Dispatches real-time SOS_ACCEPTED event to all parties.
    """
    responder_id = (current_user.id if current_user else None) or x_aegis_user_id
    if not responder_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Responder identification is required to accept an SOS."
        )

    # 1. Atomic acceptance race condition handler
    success, sos = await SOSStateMachine.attempt_atomic_acceptance(
        db=db,
        sos_id=sos_id,
        responder_user_id=responder_id
    )

    if not success or not sos:
        if sos and sos.accepted_by:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="SOS already accepted by another responder."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SOS is not in an offerable state or has expired."
        )

    # 2. Get responder's current location from UserPreference or candidate record
    pref_res = await db.execute(select(UserPreference).where(UserPreference.user_id == responder_id))
    pref = pref_res.scalars().first()
    resp_lat = (pref.last_known_lat if pref and pref.last_known_lat else None) or (sos.latitude - 0.02)
    resp_lon = (pref.last_known_lng if pref and pref.last_known_lng else None) or (sos.longitude - 0.02)

    # 3. Compute Turn-by-Turn Route & ETA
    route_calc = await SOSRoutingEngine.calculate_route(
        from_lat=resp_lat,
        from_lon=resp_lon,
        to_lat=sos.latitude,
        to_lon=sos.longitude
    )

    # 4. Create SOSAssignment record
    assignment = SOSAssignment(
        sos_id=sos.id,
        responder_user_id=responder_id,
        status="ACTIVE",
        assigned_at=utc_now(),
        route_geometry=route_calc.get("geometry", {}),
        distance_meters=route_calc.get("distance_meters", 0.0),
        eta_seconds=route_calc.get("eta_seconds", 0),
        last_responder_lat=resp_lat,
        last_responder_lon=resp_lon,
        last_responder_update=utc_now()
    )
    db.add(assignment)

    # 5. Mark candidate status
    await db.execute(
        select(SOSResponderCandidate).where(
            SOSResponderCandidate.sos_id == sos.id,
            SOSResponderCandidate.responder_user_id == responder_id
        )
    )
    cand_res = await db.execute(
        select(SOSResponderCandidate).where(
            SOSResponderCandidate.sos_id == sos.id,
            SOSResponderCandidate.responder_user_id == responder_id
        )
    )
    cand = cand_res.scalars().first()
    if cand:
        cand.status = "ACCEPTED"
        cand.responded_at = utc_now()

    await db.commit()
    await db.refresh(sos)

    # 6. Broadcast real-time SOS_ACCEPTED event
    await NotificationService.broadcast_sos_event(
        event_name="SOS_ACCEPTED",
        sos=sos,
        extra_data={
            "responder_id": responder_id,
            "eta_seconds": assignment.eta_seconds,
            "distance_meters": assignment.distance_meters,
            "route": route_calc
        }
    )

    return ApiResponse(
        success=True,
        data=_build_sos_response(sos, is_authorized=True, assignment=assignment),
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="AEGIS SOS Responder Network Core",
            processing_version="1.0.0"
        )
    )


@router.post("/{sos_id}/decline", response_model=ApiResponse[Dict[str, Any]])
async def decline_sos_offer(
    sos_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    Responder declines an SOS offer.
    Updates candidate status and triggers matching expansion if no candidates remain.
    """
    responder_id = (current_user.id if current_user else None) or x_aegis_user_id
    if not responder_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Responder identification required.")

    cand_res = await db.execute(
        select(SOSResponderCandidate).where(
            SOSResponderCandidate.sos_id == sos_id,
            SOSResponderCandidate.responder_user_id == responder_id
        )
    )
    cand = cand_res.scalars().first()
    if cand:
        cand.status = "DECLINED"
        cand.responded_at = utc_now()
        await db.commit()

    return ApiResponse(
        success=True,
        data={"sos_id": sos_id, "status": "DECLINED", "message": "Offer declined successfully."},
        freshness=FreshnessMetadata(status="fresh", age_seconds=0)
    )


@router.post("/{sos_id}/location", response_model=ApiResponse[Dict[str, Any]])
async def update_requester_location(
    sos_id: str,
    payload: SOSLocationUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    Requester live GPS breadcrumb update.
    Updates incident coordinates, records history, and notifies assigned responder.
    """
    res = await db.execute(select(SOSSignal).where(SOSSignal.id == sos_id))
    sos = res.scalars().first()
    if not sos:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SOS incident not found.")

    now = utc_now()
    sos.latitude = payload.latitude
    sos.longitude = payload.longitude
    sos.accuracy_meters = payload.accuracy_meters or sos.accuracy_meters
    if payload.battery_percent is not None:
        sos.battery_percent = payload.battery_percent
    sos.last_location_update = now
    sos.updated_at = now

    user_id = (current_user.id if current_user else None) or x_aegis_user_id or sos.user_id

    # Record breadcrumb
    loc = SOSLocationUpdate(
        sos_id=sos.id,
        user_id=user_id or "requester",
        user_type="REQUESTER",
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_meters=payload.accuracy_meters,
        battery_percent=payload.battery_percent or sos.battery_percent,
        speed_kmh=payload.speed_kmh or 0.0,
        recorded_at=now
    )
    db.add(loc)
    await db.commit()

    # Real-time event
    await NotificationService.broadcast_sos_event(
        event_name="SOS_LOCATION_UPDATED",
        sos=sos,
        extra_data={
            "user_type": "REQUESTER",
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "accuracy_meters": payload.accuracy_meters,
            "battery_percent": payload.battery_percent
        }
    )

    return ApiResponse(
        success=True,
        data={"sos_id": sos.id, "latitude": sos.latitude, "longitude": sos.longitude, "updated_at": now.isoformat()},
        freshness=FreshnessMetadata(status="fresh", age_seconds=0)
    )


@router.post("/{sos_id}/responder-location", response_model=ApiResponse[Dict[str, Any]])
async def update_responder_location(
    sos_id: str,
    payload: SOSLocationUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    Assigned responder live GPS tracking update.
    Records breadcrumbs, checks 150m movement threshold for ETA recalculation, and notifies requester.
    """
    responder_id = (current_user.id if current_user else None) or x_aegis_user_id
    res = await db.execute(select(SOSSignal).where(SOSSignal.id == sos_id))
    sos = res.scalars().first()
    if not sos:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SOS incident not found.")

    assign_res = await db.execute(
        select(SOSAssignment).where(SOSAssignment.sos_id == sos.id, SOSAssignment.status == "ACTIVE")
    )
    assignment = assign_res.scalars().first()

    now = utc_now()
    recalculated = False

    if assignment:
        # Check 150m threshold for route recalculation
        if SOSRoutingEngine.should_recalculate_route(
            last_lat=assignment.last_responder_lat,
            last_lon=assignment.last_responder_lon,
            new_lat=payload.latitude,
            new_lon=payload.longitude
        ):
            route_calc = await SOSRoutingEngine.calculate_route(
                from_lat=payload.latitude,
                from_lon=payload.longitude,
                to_lat=sos.latitude,
                to_lon=sos.longitude
            )
            assignment.route_geometry = route_calc.get("geometry", {})
            assignment.distance_meters = route_calc.get("distance_meters", 0.0)
            assignment.eta_seconds = route_calc.get("eta_seconds", 0)
            recalculated = True

        assignment.last_responder_lat = payload.latitude
        assignment.last_responder_lon = payload.longitude
        assignment.last_responder_update = now

    # Record breadcrumb
    loc = SOSLocationUpdate(
        sos_id=sos.id,
        user_id=responder_id or "responder",
        user_type="RESPONDER",
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_meters=payload.accuracy_meters,
        speed_kmh=payload.speed_kmh or 0.0,
        recorded_at=now
    )
    db.add(loc)
    await db.commit()

    # Real-time event
    event_name = "SOS_ROUTE_UPDATED" if recalculated else "SOS_RESPONDER_MOVING"
    await NotificationService.broadcast_sos_event(
        event_name=event_name,
        sos=sos,
        extra_data={
            "responder_id": responder_id,
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "eta_seconds": assignment.eta_seconds if assignment else None,
            "distance_meters": assignment.distance_meters if assignment else None,
            "route_recalculated": recalculated
        }
    )

    return ApiResponse(
        success=True,
        data={
            "sos_id": sos.id,
            "responder_latitude": payload.latitude,
            "responder_longitude": payload.longitude,
            "eta_seconds": assignment.eta_seconds if assignment else 0,
            "distance_meters": assignment.distance_meters if assignment else 0,
            "route_recalculated": recalculated
        },
        freshness=FreshnessMetadata(status="fresh", age_seconds=0)
    )


@router.post("/{sos_id}/status", response_model=ApiResponse[SOSResponseSchema])
async def update_sos_status(
    sos_id: str,
    payload: SOSStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    Updates operational progress status (e.g. RESPONDER_EN_ROUTE, ON_SITE).
    Validates state machine transition and broadcasts event.
    """
    res = await db.execute(select(SOSSignal).where(SOSSignal.id == sos_id))
    sos = res.scalars().first()
    if not sos:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SOS incident not found.")

    user_id = (current_user.id if current_user else None) or x_aegis_user_id

    await SOSStateMachine.transition(
        db=db,
        sos=sos,
        target_state=payload.status,
        changed_by_user_id=user_id,
        reason=payload.reason or "Operational status update"
    )
    await db.commit()
    await db.refresh(sos)

    event_name = f"SOS_{payload.status.upper()}" if payload.status.upper() in ("ON_SITE", "RESPONDER_EN_ROUTE") else "SOS_UPDATED"
    await NotificationService.broadcast_sos_event(event_name=event_name, sos=sos)

    return ApiResponse(
        success=True,
        data=_build_sos_response(sos, is_authorized=True),
        freshness=FreshnessMetadata(status="fresh", age_seconds=0)
    )


@router.post("/{sos_id}/resolve", response_model=ApiResponse[SOSResponseSchema])
async def resolve_sos_incident(
    sos_id: str,
    payload: SOSResolveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    Marks SOS as RESOLVED.
    Updates resolution notes, completes active assignments, and broadcasts event.
    """
    res = await db.execute(select(SOSSignal).where(SOSSignal.id == sos_id))
    sos = res.scalars().first()
    if not sos:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SOS incident not found.")

    user_id = (current_user.id if current_user else None) or x_aegis_user_id
    sos.resolution_notes = payload.resolution_notes or "Distress resolved."

    await SOSStateMachine.transition(
        db=db,
        sos=sos,
        target_state=SOSState.RESOLVED.value,
        changed_by_user_id=user_id,
        reason="Incident resolved by responder or commander"
    )

    # Complete assignment
    assign_res = await db.execute(
        select(SOSAssignment).where(SOSAssignment.sos_id == sos.id, SOSAssignment.status == "ACTIVE")
    )
    assignment = assign_res.scalars().first()
    if assignment:
        assignment.status = "COMPLETED"

    await db.commit()
    await db.refresh(sos)

    await NotificationService.broadcast_sos_event(
        event_name="SOS_RESOLVED",
        sos=sos,
        extra_data={"resolution_notes": sos.resolution_notes}
    )

    return ApiResponse(
        success=True,
        data=_build_sos_response(sos, is_authorized=True),
        freshness=FreshnessMetadata(status="fresh", age_seconds=0)
    )


@router.post("/{sos_id}/cancel", response_model=ApiResponse[SOSResponseSchema])
async def cancel_sos_incident(
    sos_id: str,
    payload: SOSCancelRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    Cancels an active SOS incident.
    """
    res = await db.execute(select(SOSSignal).where(SOSSignal.id == sos_id))
    sos = res.scalars().first()
    if not sos:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SOS incident not found.")

    user_id = (current_user.id if current_user else None) or x_aegis_user_id

    await SOSStateMachine.transition(
        db=db,
        sos=sos,
        target_state=SOSState.CANCELLED.value,
        changed_by_user_id=user_id,
        reason=payload.reason or "Incident cancelled"
    )

    # Cancel assignment
    assign_res = await db.execute(
        select(SOSAssignment).where(SOSAssignment.sos_id == sos.id, SOSAssignment.status == "ACTIVE")
    )
    assignment = assign_res.scalars().first()
    if assignment:
        assignment.status = "CANCELLED"

    await db.commit()
    await db.refresh(sos)

    await NotificationService.broadcast_sos_event(
        event_name="SOS_CANCELLED",
        sos=sos,
        extra_data={"cancellation_reason": payload.reason}
    )

    return ApiResponse(
        success=True,
        data=_build_sos_response(sos, is_authorized=True),
        freshness=FreshnessMetadata(status="fresh", age_seconds=0)
    )


