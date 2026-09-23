"""
AEGIS UNIFIED DATA CORE - Authoritative Community & Incident Reports API
/api/v1/reports
Single Source of Truth for Citizen Incident Reporting across Web (Portal) and Mobile App.
Provides full verification lifecycle, media object storage, SOS/incident linking,
and strict taxonomy distinguishing community reports from official alerts.
"""
import os
import uuid
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Header, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, or_, and_

from backend.app.database.session import get_db
import hashlib
from backend.app.database.models import IncidentReport, ReportVote, ActivityEvent, ReportEvidence, ReportVerification, User, utc_now
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.providers.adapters.geographic import GeographicLocationProvider
from backend.app.ingestion.deduplicator import EventDeduplicator
from backend.app.realtime.manager import EventBroker
from backend.app.notifications.service import PushNotificationService
from backend.app.api.deps import rate_limit_check, get_current_user
from backend.app.utils.logger import logger

router = APIRouter(prefix="/reports", tags=["Community Incident Reports"])

# Standardized Categories
SUPPORTED_CATEGORIES = {
    "FLOOD": "Flood",
    "FIRE": "Fire",
    "ROAD_BLOCKED": "Road Blocked",
    "BLOCKED_ROAD": "Road Blocked",
    "LANDSLIDE": "Landslide",
    "BUILDING_DAMAGE": "Building Damage",
    "DAMAGED_INFRASTRUCTURE": "Building Damage",
    "WATERLOGGING": "Waterlogging",
    "POWER_FAILURE": "Power Failure",
    "MISSING_PERSON": "Missing Person",
    "SEVERE_WEATHER": "Severe Weather",
    "OTHER": "Other"
}


class ReportCreateRequest(BaseModel):
    category: Optional[str] = Field(default=None, description="FLOOD, FIRE, ROAD_BLOCKED, LANDSLIDE, BUILDING_DAMAGE, WATERLOGGING, POWER_FAILURE, MISSING_PERSON, OTHER")
    hazard_type: Optional[str] = Field(default=None, description="Synonym for category")
    title: str = Field(..., min_length=3, max_length=255, description="Brief summary")
    description: str = Field(..., min_length=5, max_length=2000, description="Detailed ground-truth observation")
    severity: str = Field(default="MODERATE", description="LOW, MODERATE, HIGH, CRITICAL")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    lng: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    lon: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    accuracy_meters: Optional[float] = Field(default=10.0, ge=0.0, le=5000.0)
    location_name: Optional[str] = Field(default="")
    city: Optional[str] = Field(default="")
    district: Optional[str] = Field(default="")
    state: Optional[str] = Field(default="")
    country: Optional[str] = Field(default="India")
    media_urls: Optional[List[str]] = Field(default_factory=list)
    media_type: Optional[str] = Field(default="NONE", description="PHOTO, VIDEO, MIXED, NONE")
    idempotency_key: Optional[str] = Field(default=None, description="Client-generated key for offline sync deduplication")
    anonymous_reporter_id: Optional[str] = Field(default=None, description="Pseudonymous device/client token")
    reporter_name: Optional[str] = Field(default="Citizen Observer")
    linked_sos_id: Optional[str] = Field(default=None, description="Optional link to active SOS beacon")
    linked_incident_id: Optional[str] = Field(default=None, description="Optional link to master hazard incident")


class ReportUpdateRequest(BaseModel):
    status: Optional[str] = Field(default=None, description="SUBMITTED, PENDING_VERIFICATION, VERIFIED, REJECTED, ACTIVE, RESOLVED, EXPIRED")
    severity: Optional[str] = Field(default=None, description="LOW, MODERATE, HIGH, CRITICAL")
    category: Optional[str] = Field(default=None, description="Updated category")
    verification_status: Optional[str] = Field(default=None, description="UNVERIFIED, VERIFIED, REJECTED")
    operator_notes: Optional[str] = Field(default=None)


class ReportVerifyRequest(BaseModel):
    severity: Optional[str] = Field(default=None, description="Optional updated severity by operator (LOW, MODERATE, HIGH, CRITICAL)")
    operator_notes: Optional[str] = Field(default="Verified by emergency operations command.", description="Operator review notes")


class ReportRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=3, description="Mandatory reason for report rejection (e.g. Duplicate, Unsubstantiated, Spam)")
    operator_notes: Optional[str] = Field(default="", description="Internal review notes")


class ReportLinkRequest(BaseModel):
    linked_sos_id: Optional[str] = Field(default=None, description="Link report to an active SOS distress beacon")
    linked_incident_id: Optional[str] = Field(default=None, description="Link report to a master hazard/disaster incident")
    operator_notes: Optional[str] = Field(default="Linked to operational incident by controller.", description="Linking audit notes")


class ReportVoteRequest(BaseModel):
    voter_id: str = Field(..., min_length=3, description="Pseudonymous client token or user ID")
    vote_type: str = Field(default="UPVOTE", description="UPVOTE or DOWNVOTE")


class ReportResponseSchema(BaseModel):
    id: str
    category: str
    hazard_type: str
    title: str
    description: str
    severity: str
    status: str
    verification_status: str
    is_verified: bool
    source: str
    source_type: str = "COMMUNITY_REPORT"  # Always COMMUNITY_REPORT, never OFFICIAL_ALERT
    provenance_label: str
    latitude: float
    longitude: float
    accuracy_meters: float
    location_name: Optional[str] = ""
    city: Optional[str] = ""
    district: Optional[str] = ""
    state: Optional[str] = ""
    country: str = "India"
    media_urls: List[str] = []
    media_type: Optional[str] = "NONE"
    upvotes: int = 0
    downvotes: int = 0
    reporter_name: Optional[str] = "Citizen Observer"
    verified_by_user_id: Optional[str] = None
    verified_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    linked_sos_id: Optional[str] = None
    linked_incident_id: Optional[str] = None
    operator_notes: Optional[str] = None
    expires_at: Optional[str] = None
    created_at: str
    updated_at: str


def map_report_to_schema(r: IncidentReport) -> ReportResponseSchema:
    v_status = (r.verification_status or "UNVERIFIED").upper()
    prov_label = "Community Report (Verified)" if r.is_verified else "Community Report (Unverified)"
    if v_status == "REJECTED":
        prov_label = "Community Report (Rejected)"

    return ReportResponseSchema(
        id=r.id,
        category=r.category or r.hazard_type or "OTHER",
        hazard_type=r.hazard_type or r.category or "OTHER",
        title=r.title,
        description=r.description,
        severity=(r.severity or "MODERATE").upper(),
        status=(r.status or "SUBMITTED").upper(),
        verification_status=v_status,
        is_verified=bool(r.is_verified),
        source=r.source or "COMMUNITY",
        source_type="COMMUNITY_REPORT",
        provenance_label=prov_label,
        latitude=r.latitude,
        longitude=r.longitude,
        accuracy_meters=r.accuracy_meters or 10.0,
        location_name=r.location_name or "",
        city=r.city or "",
        district=r.district or "",
        state=r.state or "",
        country=r.country or "India",
        media_urls=r.media_urls or [],
        media_type=r.media_type or "NONE",
        upvotes=r.upvotes or 0,
        downvotes=r.downvotes or 0,
        reporter_name=r.reporter_name or "Citizen Observer",
        verified_by_user_id=r.verified_by_user_id,
        verified_at=r.verified_at.isoformat() if r.verified_at else None,
        rejection_reason=r.rejection_reason if r.rejection_reason else None,
        linked_sos_id=r.linked_sos_id,
        linked_incident_id=r.linked_incident_id,
        operator_notes=r.operator_notes,
        expires_at=r.expires_at.isoformat() if r.expires_at else None,
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
    )


@router.post("", response_model=ApiResponse[ReportResponseSchema], dependencies=[Depends(rate_limit_check)])
async def create_community_report(
    payload: ReportCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    Submit a ground-truth citizen incident report.
    Supports all 9 standard categories: Flood, Fire, Road Blocked, Landslide, Building Damage,
    Waterlogging, Power Failure, Missing Person, Other.
    Initial state is SUBMITTED with verification_status: UNVERIFIED.
    """
    resolved_lon = payload.longitude if payload.longitude is not None else (payload.lng if payload.lng is not None else payload.lon)
    if resolved_lon is None:
        raise HTTPException(status_code=422, detail="Missing required longitude coordinate.")

    now = utc_now()
    user_id = (current_user.id if current_user else None) or x_aegis_user_id

    # 1. Check Idempotency Key (Offline Sync Protection)
    if payload.idempotency_key:
        existing = await db.execute(
            select(IncidentReport).where(IncidentReport.idempotency_key == payload.idempotency_key)
        )
        existing_report = existing.scalars().first()
        if existing_report:
            logger.info(f"Idempotent report submission matched existing ID: {existing_report.id}")
            return ApiResponse(
                success=True,
                data=map_report_to_schema(existing_report),
                freshness=FreshnessMetadata(status="fresh", age_seconds=0),
                provenance=ProvenanceMetadata(
                    data_type="community_report",
                    source_authority="AEGIS Single Source of Truth",
                    processing_version="2.4.0"
                )
            )

    # 2. Category & Severity Normalization
    cat_input = payload.category or payload.hazard_type or "OTHER"
    raw_cat = cat_input.upper().replace(" ", "_")
    cat = raw_cat if raw_cat in SUPPORTED_CATEGORIES else "OTHER"
    sev = (payload.severity or "MODERATE").upper()
    if sev not in ["LOW", "MODERATE", "HIGH", "CRITICAL"]:
        sev = "MODERATE"

    # 3. Offline Reverse Geocoding
    city_name = payload.city or ""
    district_name = payload.district or ""
    state_name = payload.state or ""
    location_name = payload.location_name or ""

    if not state_name or not district_name:
        geo = GeographicLocationProvider.reverse_geocode_offline(payload.latitude, resolved_lon)
        city_name = city_name or geo.get("district") or ""
        district_name = district_name or geo.get("district") or ""
        state_name = state_name or geo.get("state") or "India"
        location_name = location_name or geo.get("formatted_address") or f"{district_name}, {state_name}"

    # Determine media type if not explicitly supplied
    m_type = payload.media_type or "NONE"
    if payload.media_urls and m_type == "NONE":
        has_video = any(u.endswith((".mp4", ".mov", ".webm", ".mkv")) for u in payload.media_urls)
        has_photo = any(u.endswith((".jpg", ".jpeg", ".png", ".webp", ".heic")) for u in payload.media_urls)
        if has_video and has_photo:
            m_type = "MIXED"
        elif has_video:
            m_type = "VIDEO"
        elif has_photo:
            m_type = "PHOTO"

    # 4. Create IncidentReport record
    new_report_id = str(uuid.uuid4())
    report = IncidentReport(
        id=new_report_id,
        user_id=user_id,
        anonymous_reporter_id=payload.anonymous_reporter_id,
        reporter_name=payload.reporter_name or (current_user.full_name if current_user else "Citizen Observer"),
        category=cat,
        hazard_type=cat,
        title=payload.title,
        description=payload.description,
        severity=sev,
        status="SUBMITTED",
        verification_status="UNVERIFIED",
        is_verified=False,
        source="COMMUNITY",
        source_type="COMMUNITY_REPORT",
        latitude=payload.latitude,
        longitude=resolved_lon,
        accuracy_meters=payload.accuracy_meters or 10.0,
        location_name=location_name,
        city=city_name,
        district=district_name,
        state=state_name,
        country=payload.country or "India",
        media_urls=payload.media_urls or [],
        media_type=m_type,
        idempotency_key=payload.idempotency_key,
        linked_sos_id=payload.linked_sos_id,
        linked_incident_id=payload.linked_incident_id,
        expires_at=now + timedelta(hours=48),
        created_at=now,
        updated_at=now
    )

    db.add(report)
    if payload.media_urls:
        for m_url in payload.media_urls:
            evidence = ReportEvidence(
                report_id=report.id,
                uploader_id=user_id,
                media_type=payload.media_type or "PHOTO",
                file_url=m_url,
                file_size_bytes=0,
                mime_type="video/mp4" if (payload.media_type == "VIDEO" or m_url.endswith((".mp4", ".mov"))) else "image/jpeg",
                is_verified=False,
                metadata_json={"source": "citizen_report_submission"},
                created_at=now
            )
            db.add(evidence)
    await db.commit()
    await db.refresh(report)

    # 5. Broadcast Real-time Event
    schema_data = map_report_to_schema(report)
    await EventBroker.publish_event(
        event_type="REPORT_CREATED",
        data=schema_data.model_dump(),
        channel="reports",
        category="COMMUNITY_REPORT"
    )

    return ApiResponse(
        success=True,
        data=schema_data,
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="community_report",
            source_authority="AEGIS Community Verification Grid",
            processing_version="2.4.0"
        )
    )


@router.get("", response_model=ApiResponse[List[ReportResponseSchema]])
async def list_community_reports(
    status: Optional[str] = Query(default=None, description="SUBMITTED, PENDING_VERIFICATION, VERIFIED, REJECTED, ACTIVE, ALL"),
    category: Optional[str] = Query(default=None, description="Filter by category"),
    hazard_type: Optional[str] = Query(default=None, description="Synonym for category"),
    severity: Optional[str] = Query(default=None, description="LOW, MODERATE, HIGH, CRITICAL"),
    verification_status: Optional[str] = Query(default=None, description="UNVERIFIED, VERIFIED, REJECTED, ALL"),
    state: Optional[str] = Query(default=None, description="Filter by state"),
    district: Optional[str] = Query(default=None, description="Filter by district"),
    bbox: Optional[str] = Query(default=None, description="min_lon,min_lat,max_lon,max_lat"),
    lat: Optional[float] = Query(default=None, ge=-90.0, le=90.0),
    lng: Optional[float] = Query(default=None, ge=-180.0, le=180.0),
    lon: Optional[float] = Query(default=None, ge=-180.0, le=180.0),
    radius_km: Optional[float] = Query(default=100.0, ge=0.1, le=2000.0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    List, filter, and search community incident reports with geospatial bounds and radial queries.
    """
    query = select(IncidentReport).order_by(desc(IncidentReport.created_at))

    # Status filter
    if status and status.upper() != "ALL":
        if status.upper() == "ACTIVE":
            query = query.where(IncidentReport.status.in_(["SUBMITTED", "PENDING_VERIFICATION", "VERIFIED", "ACTIVE"]))
        else:
            query = query.where(func.upper(IncidentReport.status) == status.upper())

    # Verification filter
    if verification_status and verification_status.upper() != "ALL":
        query = query.where(func.upper(IncidentReport.verification_status) == verification_status.upper())

    # Category filter
    target_cat = category or hazard_type
    if target_cat:
        query = query.where(func.upper(IncidentReport.category) == target_cat.upper())

    # Severity filter
    if severity:
        query = query.where(func.upper(IncidentReport.severity) == severity.upper())

    # Geographic filters
    if state:
        query = query.where(IncidentReport.state.ilike(f"%{state}%"))
    if district:
        query = query.where(IncidentReport.district.ilike(f"%{district}%"))

    # Bounding box filter
    if bbox:
        try:
            parts = [float(p.strip()) for p in bbox.split(",")]
            if len(parts) == 4:
                min_lon, min_lat, max_lon, max_lat = parts
                query = query.where(
                    IncidentReport.longitude >= min_lon,
                    IncidentReport.longitude <= max_lon,
                    IncidentReport.latitude >= min_lat,
                    IncidentReport.latitude <= max_lat
                )
        except Exception:
            pass

    query = query.limit(limit * 3 if (lat and (lng or lon)) else limit).offset(offset)
    res = await db.execute(query)
    rows = res.scalars().all()

    resolved_lon = lng if lng is not None else lon
    items: List[ReportResponseSchema] = []
    for r in rows:
        if lat is not None and resolved_lon is not None:
            dist = EventDeduplicator.haversine_distance_km(lat, resolved_lon, r.latitude, r.longitude)
            if dist > (radius_km or 100.0):
                continue

        items.append(map_report_to_schema(r))
        if len(items) >= limit:
            break

    return ApiResponse(
        success=True,
        data=items,
        freshness=FreshnessMetadata(status="fresh", age_seconds=5),
        provenance=ProvenanceMetadata(
            data_type="community_report",
            source_authority="AEGIS Single Source of Truth",
            processing_version="2.4.0"
        )
    )


@router.get("/{report_id}", response_model=ApiResponse[ReportResponseSchema])
async def get_report_by_id(
    report_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Fetch complete details for a single community report."""
    res = await db.execute(select(IncidentReport).where(IncidentReport.id == report_id))
    report = res.scalars().first()
    if not report:
        raise HTTPException(status_code=404, detail="Community report not found.")

    return ApiResponse(
        success=True,
        data=map_report_to_schema(report),
        freshness=FreshnessMetadata(status="fresh", age_seconds=5),
        provenance=ProvenanceMetadata(
            data_type="community_report",
            source_authority="AEGIS Single Source of Truth",
            processing_version="2.4.0"
        )
    )


@router.post("/{report_id}/verify", response_model=ApiResponse[ReportResponseSchema])
async def verify_community_report(
    report_id: str,
    payload: Optional[ReportVerifyRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    OPERATOR VERIFICATION ENDPOINT:
    Verifies a citizen community report, sets verification_status = VERIFIED, is_verified = True,
    records verified_by_user_id, verified_at, and broadcasts real-time REPORT_VERIFIED event.
    """
    res = await db.execute(select(IncidentReport).where(IncidentReport.id == report_id))
    report = res.scalars().first()
    if not report:
        raise HTTPException(status_code=404, detail="Community report not found.")

    user_id = (current_user.id if current_user else None) or x_aegis_user_id or "operator"
    now = utc_now()

    report.status = "VERIFIED"
    report.verification_status = "VERIFIED"
    report.is_verified = True
    report.verified_by_user_id = user_id
    report.verified_at = now
    if payload:
        if payload.severity:
            report.severity = payload.severity.upper()
        if payload.operator_notes:
            report.operator_notes = payload.operator_notes
    report.updated_at = now

    ver_log = ReportVerification(
        report_id=report.id,
        operator_id=user_id if user_id and len(user_id) == 36 else "00000000-0000-0000-0000-000000000000",
        verification_status="VERIFIED",
        verified_severity=report.severity,
        operator_notes=payload.operator_notes if payload else "Verified by operator command.",
        confidence_score=1.0,
        created_at=now
    )
    db.add(ver_log)

    await db.commit()
    await db.refresh(report)

    schema_data = map_report_to_schema(report)

    # Broadcast event
    await EventBroker.publish_event(
        event_type="REPORT_VERIFIED",
        data=schema_data.model_dump(),
        channel="reports",
        category="COMMUNITY_REPORT"
    )

    # Dispatch mobile push notification to original reporter
    await PushNotificationService.dispatch_report_verification(db, report)

    return ApiResponse(
        success=True,
        data=schema_data,
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="community_report",
            source_authority="AEGIS Operations Verification Center",
            processing_version="2.4.0"
        )
    )


@router.post("/{report_id}/reject", response_model=ApiResponse[ReportResponseSchema])
async def reject_community_report(
    report_id: str,
    payload: ReportRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    OPERATOR REJECTION ENDPOINT:
    Rejects a community report with a mandatory reason (e.g. False alarm, Spam, Duplicate).
    Sets status = REJECTED, verification_status = REJECTED, is_verified = False.
    """
    res = await db.execute(select(IncidentReport).where(IncidentReport.id == report_id))
    report = res.scalars().first()
    if not report:
        raise HTTPException(status_code=404, detail="Community report not found.")

    user_id = (current_user.id if current_user else None) or x_aegis_user_id or "operator"
    now = utc_now()

    report.status = "REJECTED"
    report.verification_status = "REJECTED"
    report.is_verified = False
    report.rejection_reason = payload.rejection_reason
    if payload.operator_notes:
        report.operator_notes = payload.operator_notes
    report.updated_at = now

    rej_log = ReportVerification(
        report_id=report.id,
        operator_id=user_id if user_id and len(user_id) == 36 else "00000000-0000-0000-0000-000000000000",
        verification_status="REJECTED",
        verified_severity=report.severity,
        rejection_reason=payload.rejection_reason,
        operator_notes=payload.operator_notes or "",
        confidence_score=0.0,
        created_at=now
    )
    db.add(rej_log)

    await db.commit()
    await db.refresh(report)

    schema_data = map_report_to_schema(report)

    # Broadcast event
    await EventBroker.publish_event(
        event_type="REPORT_REJECTED",
        data=schema_data.model_dump(),
        channel="reports",
        category="COMMUNITY_REPORT"
    )

    return ApiResponse(
        success=True,
        data=schema_data,
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="community_report",
            source_authority="AEGIS Operations Moderation Center",
            processing_version="2.4.0"
        )
    )


@router.post("/{report_id}/link", response_model=ApiResponse[ReportResponseSchema])
async def link_community_report(
    report_id: str,
    payload: ReportLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    x_aegis_user_id: Optional[str] = Header(default=None, alias="X-Aegis-User-Id")
):
    """
    OPERATOR INCIDENT & SOS LINKING ENDPOINT:
    Cross-links a citizen community report to an active SOS distress beacon or master disaster incident.
    """
    res = await db.execute(select(IncidentReport).where(IncidentReport.id == report_id))
    report = res.scalars().first()
    if not report:
        raise HTTPException(status_code=404, detail="Community report not found.")

    now = utc_now()
    if payload.linked_sos_id is not None:
        report.linked_sos_id = payload.linked_sos_id
    if payload.linked_incident_id is not None:
        report.linked_incident_id = payload.linked_incident_id
    if payload.operator_notes:
        report.operator_notes = payload.operator_notes
    report.updated_at = now

    await db.commit()
    await db.refresh(report)

    schema_data = map_report_to_schema(report)

    await EventBroker.publish_event(
        event_type="REPORT_LINKED",
        data=schema_data.model_dump(),
        channel="reports",
        category="COMMUNITY_REPORT"
    )

    return ApiResponse(
        success=True,
        data=schema_data,
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="community_report",
            source_authority="AEGIS Operations Command",
            processing_version="2.4.0"
        )
    )


@router.patch("/{report_id}", response_model=ApiResponse[ReportResponseSchema])
async def update_report_status(
    report_id: str,
    payload: ReportUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Moderates or updates status and severity of an existing report.
    """
    res = await db.execute(select(IncidentReport).where(IncidentReport.id == report_id))
    report = res.scalars().first()
    if not report:
        raise HTTPException(status_code=404, detail="Community report not found.")

    if payload.status:
        report.status = payload.status.upper()
    if payload.severity:
        report.severity = payload.severity.upper()
    if payload.category:
        report.category = payload.category.upper()
        report.hazard_type = payload.category.upper()
    if payload.verification_status:
        report.verification_status = payload.verification_status.upper()
        if report.verification_status in ["VERIFIED", "VERIFIED_COMMUNITY", "OFFICIAL"]:
            report.is_verified = True
        elif report.verification_status == "REJECTED":
            report.is_verified = False
    if payload.operator_notes is not None:
        report.operator_notes = payload.operator_notes

    report.updated_at = utc_now()
    await db.commit()
    await db.refresh(report)

    schema_data = map_report_to_schema(report)

    await EventBroker.publish_event(
        event_type="REPORT_UPDATED",
        data=schema_data.model_dump(),
        channel="reports",
        category="COMMUNITY_REPORT"
    )

    return ApiResponse(
        success=True,
        data=schema_data,
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="community_report",
            source_authority="AEGIS Single Source of Truth",
            processing_version="2.4.0"
        )
    )


@router.post("/{report_id}/vote", response_model=ApiResponse[ReportResponseSchema])
async def vote_community_report(
    report_id: str,
    payload: ReportVoteRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Cast an upvote or downvote on a community report.
    Automatically elevates report trust to VERIFIED when upvote threshold is reached.
    """
    res = await db.execute(select(IncidentReport).where(IncidentReport.id == report_id))
    report = res.scalars().first()
    if not report:
        raise HTTPException(status_code=404, detail="Community report not found.")

    v_type = payload.vote_type.upper()
    if v_type not in ["UPVOTE", "DOWNVOTE"]:
        raise HTTPException(status_code=400, detail="vote_type must be 'UPVOTE' or 'DOWNVOTE'.")

    v_res = await db.execute(
        select(ReportVote).where(ReportVote.report_id == report_id, ReportVote.voter_id == payload.voter_id)
    )
    existing_vote = v_res.scalars().first()

    if existing_vote:
        if existing_vote.vote_type != v_type:
            existing_vote.vote_type = v_type
            if v_type == "UPVOTE":
                report.upvotes = max(0, (report.upvotes or 0) + 1)
                report.downvotes = max(0, (report.downvotes or 0) - 1)
            else:
                report.downvotes = max(0, (report.downvotes or 0) + 1)
                report.upvotes = max(0, (report.upvotes or 0) - 1)
    else:
        new_vote = ReportVote(report_id=report_id, voter_id=payload.voter_id, vote_type=v_type)
        db.add(new_vote)
        if v_type == "UPVOTE":
            report.upvotes = (report.upvotes or 0) + 1
        else:
            report.downvotes = (report.downvotes or 0) + 1

    # Automatic community verification threshold
    if (report.upvotes or 0) >= 3 and (report.upvotes or 0) > ((report.downvotes or 0) * 2):
        report.verification_status = "VERIFIED"
        report.is_verified = True
        report.status = "VERIFIED"

    report.updated_at = utc_now()
    await db.commit()
    await db.refresh(report)

    schema_data = map_report_to_schema(report)

    await EventBroker.publish_event(
        event_type="REPORT_UPDATED",
        data=schema_data.model_dump(),
        channel="reports",
        category="COMMUNITY_REPORT"
    )

    return ApiResponse(
        success=True,
        data=schema_data,
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="community_report",
            source_authority="AEGIS Community Verification Grid",
            processing_version="2.4.0"
        )
    )


@router.post("/sync", response_model=ApiResponse[List[ReportResponseSchema]])
async def batch_sync_offline_reports(
    reports: List[ReportCreateRequest],
    db: AsyncSession = Depends(get_db)
):
    """
    Batch synchronization endpoint for mobile offline queue.
    Uses client idempotency keys to guarantee zero duplicate submissions.
    """
    synced: List[ReportResponseSchema] = []
    for r_req in reports:
        resp = await create_community_report(r_req, db)
        if resp.data:
            synced.append(resp.data)

    return ApiResponse(
        success=True,
        data=synced,
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="community_report_sync",
            source_authority="AEGIS Offline Sync Engine",
            processing_version="2.4.0"
        )
    )


class MediaUploadResponse(BaseModel):
    url: str
    filename: str
    content_type: str
    size_bytes: int
    media_type: str
    sha256_hash: Optional[str] = None  # PHOTO or VIDEO


@router.post("/upload-media", response_model=ApiResponse[MediaUploadResponse], dependencies=[Depends(rate_limit_check)])
async def upload_report_media(
    file: UploadFile = File(...),
    category: Optional[str] = Form(default="report_media")
):
    """
    Secure incident report media upload endpoint for photos and video evidence.
    Supports image/jpeg, image/png, image/webp, image/heic, video/mp4, video/quicktime, video/webm.
    Enforces 50MB max file size for videos, 10MB for photos.
    """
    ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif"}
    ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm", "video/x-matroska"}
    ALLOWED_MIME_TYPES = ALLOWED_IMAGE_TYPES.union(ALLOWED_VIDEO_TYPES)

    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
    MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB

    content_type = (file.content_type or "").lower()
    ext = os.path.splitext(file.filename or "")[1].lower()
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov", ".webm", ".heic", ".mkv"}

    if content_type not in ALLOWED_MIME_TYPES and ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported media format '{content_type or ext}'. Supported: JPEG, PNG, WEBP, GIF, HEIC, MP4, MOV, WEBM, MKV."
        )

    contents = await file.read()
    size_bytes = len(contents)
    sha256_hash = hashlib.sha256(contents).hexdigest()

    if size_bytes == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    is_video = (content_type in ALLOWED_VIDEO_TYPES) or (ext in {".mp4", ".mov", ".webm", ".mkv"})
    max_size = MAX_VIDEO_SIZE if is_video else MAX_IMAGE_SIZE
    media_label = "VIDEO" if is_video else "PHOTO"

    if size_bytes > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"{media_label} file size ({size_bytes / (1024*1024):.1f}MB) exceeds maximum permitted limit of {max_size // (1024*1024)}MB."
        )

    safe_ext = re.sub(r'[^a-zA-Z0-9.]', '', ext) or (".mp4" if is_video else ".jpg")
    unique_filename = f"incident_{uuid.uuid4().hex[:12]}_{int(utc_now().timestamp())}{safe_ext}"

    static_dir = Path(__file__).resolve().parent.parent.parent.parent / "static" / "uploads"
    os.makedirs(static_dir, exist_ok=True)
    target_path = static_dir / unique_filename

    with open(target_path, "wb") as f:
        f.write(contents)

    media_url = f"/static/uploads/{unique_filename}"
    logger.info(f"Stored {media_label} media: {unique_filename} ({size_bytes} bytes)")

    return ApiResponse(
        success=True,
        data=MediaUploadResponse(
            url=media_url,
            filename=unique_filename,
            content_type=content_type or ("video/mp4" if is_video else "image/jpeg"),
            size_bytes=size_bytes,
            media_type=media_label,
            sha256_hash=sha256_hash
        ),
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="report_media_asset",
            source_authority="AEGIS Secure Asset Vault",
            processing_version="2.0.0"
        )
    )
