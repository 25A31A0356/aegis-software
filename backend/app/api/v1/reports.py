"""
AEGIS UNIFIED DATA CORE - Authoritative Community & Incident Reports API
/api/v1/reports
Single Source of Truth for Aegis Web (Portal) and Aegis App (Mobile Alert).
"""
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from backend.app.database.session import get_db
from backend.app.database.models import IncidentReport, ReportVote, ActivityEvent
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.providers.adapters.geographic import GeographicLocationProvider
from backend.app.ingestion.deduplicator import EventDeduplicator
from backend.app.realtime.manager import EventBroker
from backend.app.api.deps import rate_limit_check
from backend.app.utils.logger import logger

router = APIRouter(prefix="/reports", tags=["Community Incident Reports"])


class ReportCreateRequest(BaseModel):
    category: Optional[str] = Field(default=None, description="FLOOD, WATERLOGGING, BLOCKED_ROAD, FALLEN_TREE, LANDSLIDE, FIRE, SEVERE_WEATHER, DAMAGED_INFRASTRUCTURE, ACCIDENT, UNSAFE_AREA, OTHER")
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
    idempotency_key: Optional[str] = Field(default=None, description="Client-generated key for offline sync deduplication")
    anonymous_reporter_id: Optional[str] = Field(default=None, description="Pseudonymous device/client token")
    reporter_name: Optional[str] = Field(default="Citizen Observer")


class ReportUpdateRequest(BaseModel):
    status: Optional[str] = Field(default=None, description="ACTIVE, VERIFIED, RESOLVED, EXPIRED")
    severity: Optional[str] = Field(default=None, description="LOW, MODERATE, HIGH, CRITICAL")
    verification_status: Optional[str] = Field(default=None, description="VERIFIED_COMMUNITY, UNVERIFIED_COMMUNITY, RESOLVED")


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
    latitude: float
    longitude: float
    accuracy_meters: float
    location_name: Optional[str] = ""
    city: Optional[str] = ""
    district: Optional[str] = ""
    state: Optional[str] = ""
    country: str = "India"
    media_urls: List[str] = []
    upvotes: int = 0
    downvotes: int = 0
    reporter_name: Optional[str] = "Citizen Observer"
    expires_at: Optional[str] = None
    created_at: str
    updated_at: str


def map_report_to_schema(r: IncidentReport) -> ReportResponseSchema:
    return ReportResponseSchema(
        id=r.id,
        category=r.category or r.hazard_type or "OTHER",
        hazard_type=r.hazard_type or r.category or "OTHER",
        title=r.title,
        description=r.description,
        severity=(r.severity or "MODERATE").upper(),
        status=(r.status or "ACTIVE").upper(),
        verification_status=(r.verification_status or "UNVERIFIED_COMMUNITY").upper(),
        is_verified=bool(r.is_verified),
        source=r.source or "COMMUNITY",
        latitude=r.latitude,
        longitude=r.longitude,
        accuracy_meters=r.accuracy_meters or 10.0,
        location_name=r.location_name or "",
        city=r.city or "",
        district=r.district or "",
        state=r.state or "",
        country=r.country or "India",
        media_urls=r.media_urls or [],
        upvotes=r.upvotes or 0,
        downvotes=r.downvotes or 0,
        reporter_name=r.reporter_name or "Citizen Observer",
        expires_at=r.expires_at.isoformat() if r.expires_at else None,
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
    )


@router.post("", response_model=ApiResponse[ReportResponseSchema], dependencies=[Depends(rate_limit_check)])
async def create_community_report(
    payload: ReportCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Submit a citizen disaster or ground-truth public safety report.
    Single authoritative entrypoint for both Web and Mobile App.
    """
    # Resolve longitude coordinate
    resolved_lon = payload.longitude if payload.longitude is not None else (payload.lng if payload.lng is not None else payload.lon)
    if resolved_lon is None:
        raise HTTPException(status_code=422, detail="Missing required longitude coordinate (provide 'longitude', 'lng', or 'lon').")

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

    # 2. Category Normalization
    cat = (payload.category or payload.hazard_type or "OTHER").upper()
    sev = (payload.severity or "MODERATE").upper()

    # 3. Reverse Geocoding if city/state not provided
    city_name = payload.city or ""
    district_name = payload.district or ""
    state_name = payload.state or ""
    loc_name = payload.location_name or ""

    if not city_name or not state_name:
        try:
            geo_provider = GeographicLocationProvider()
            geo_data = await geo_provider.reverse_geocode(payload.latitude, resolved_lon)
            if not city_name:
                city_name = geo_data.get("locality") or geo_data.get("district") or ""
            if not district_name:
                district_name = geo_data.get("district") or ""
            if not state_name:
                state_name = geo_data.get("state") or ""
            if not loc_name:
                loc_name = geo_data.get("name") or f"{city_name}, {state_name}"
        except Exception as e:
            logger.debug(f"Reverse geocode lookup bypassed: {e}")

    # 4. Compute Expiry Window based on severity
    expiry_hours = {
        "CRITICAL": 72,
        "HIGH": 48,
        "MODERATE": 24,
        "LOW": 12
    }.get(sev, 24)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)

    # 5. Persist Community Report to Authoritative Database
    report = IncidentReport(
        anonymous_reporter_id=payload.anonymous_reporter_id,
        reporter_name=payload.reporter_name or "Citizen Observer",
        category=cat,
        hazard_type=cat,
        title=payload.title.strip(),
        description=payload.description.strip(),
        severity=sev,
        status="ACTIVE",
        verification_status="UNVERIFIED_COMMUNITY",
        is_verified=False,
        verification_source="CITIZEN_SUBMISSION",
        source="COMMUNITY",
        latitude=payload.latitude,
        longitude=resolved_lon,
        accuracy_meters=payload.accuracy_meters or 10.0,
        location_name=loc_name,
        city=city_name,
        district=district_name,
        state=state_name,
        country=payload.country or "India",
        media_urls=payload.media_urls or [],
        upvotes=0,
        downvotes=0,
        idempotency_key=payload.idempotency_key,
        expires_at=expires_at
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    # 6. Log Activity Event
    activity = ActivityEvent(
        event_type="REPORT_CREATED",
        entity_type="COMMUNITY_REPORT",
        entity_id=report.id,
        title=report.title,
        description=report.description,
        category=report.category,
        severity=report.severity,
        latitude=report.latitude,
        longitude=report.longitude,
        location_name=report.location_name,
        city=report.city,
        state=report.state,
        source="COMMUNITY",
        verification_status=report.verification_status,
        payload={
            "report_id": report.id,
            "media_count": len(report.media_urls),
            "upvotes": 0,
            "expires_at": report.expires_at.isoformat() if report.expires_at else None
        }
    )
    db.add(activity)
    await db.commit()

    schema_data = map_report_to_schema(report)

    # 7. Broadcast Real-Time Event to all Web and App clients
    await EventBroker.publish_event(
        event_type="REPORT_CREATED",
        data=schema_data.model_dump(),
        channel="reports",
        category="COMMUNITY_REPORT"
    )

    logger.info(f"Community report created successfully: ID={report.id}, Category={report.category}, Location=({report.latitude}, {report.longitude})")

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


@router.get("", response_model=ApiResponse[List[ReportResponseSchema]])
async def list_community_reports(
    category: Optional[str] = Query(default="ALL", description="Category filter (FLOOD, BLOCKED_ROAD, FIRE, etc.)"),
    hazard_type: Optional[str] = Query(default=None, description="Synonym for category"),
    severity: Optional[str] = Query(default="ALL", description="LOW, MODERATE, HIGH, CRITICAL"),
    status: Optional[str] = Query(default="ALL", description="ACTIVE, VERIFIED, RESOLVED, ALL"),
    verification_status: Optional[str] = Query(default="ALL", description="OFFICIAL, COMMUNITY, VERIFIED_COMMUNITY, ALL"),
    lat: Optional[float] = Query(default=None, ge=-90.0, le=90.0),
    lng: Optional[float] = Query(default=None, ge=-180.0, le=180.0),
    lon: Optional[float] = Query(default=None, ge=-180.0, le=180.0),
    radius_km: Optional[float] = Query(default=100.0, ge=1.0, le=1000.0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    List authoritative community incident reports with rich spatial and status filtering.
    """
    query = select(IncidentReport).order_by(desc(IncidentReport.created_at))

    # Category filter
    target_cat = category if category != "ALL" else (hazard_type if hazard_type and hazard_type != "ALL" else None)
    if target_cat:
        query = query.where(
            (IncidentReport.category == target_cat.upper()) | (IncidentReport.hazard_type == target_cat.upper())
        )

    # Severity filter
    if severity and severity.upper() != "ALL":
        query = query.where(func.upper(IncidentReport.severity) == severity.upper())

    # Status filter
    if status and status.upper() != "ALL":
        query = query.where(func.upper(IncidentReport.status) == status.upper())

    # Verification status filter
    if verification_status and verification_status.upper() != "ALL":
        query = query.where(func.upper(IncidentReport.verification_status) == verification_status.upper())

    query = query.limit(limit * 3 if (lat and (lng or lon)) else limit).offset(offset)
    res = await db.execute(query)
    rows = res.scalars().all()

    # Spatial proximity filter
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


@router.patch("/{report_id}", response_model=ApiResponse[ReportResponseSchema])
async def update_report_status(
    report_id: str,
    payload: ReportUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Moderates or updates status of an existing report (VERIFIED, RESOLVED, EXPIRED).
    """
    res = await db.execute(select(IncidentReport).where(IncidentReport.id == report_id))
    report = res.scalars().first()
    if not report:
        raise HTTPException(status_code=404, detail="Community report not found.")

    if payload.status:
        report.status = payload.status.upper()
    if payload.severity:
        report.severity = payload.severity.upper()
    if payload.verification_status:
        report.verification_status = payload.verification_status.upper()
        if report.verification_status in ["VERIFIED_COMMUNITY", "OFFICIAL"]:
            report.is_verified = True

    report.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(report)

    # Activity log
    activity_type = "REPORT_RESOLVED" if report.status == "RESOLVED" else ("REPORT_VERIFIED" if report.is_verified else "REPORT_UPDATED")
    activity = ActivityEvent(
        event_type=activity_type,
        entity_type="COMMUNITY_REPORT",
        entity_id=report.id,
        title=f"Report Updated: {report.title}",
        description=f"Report status changed to {report.status} ({report.verification_status})",
        category=report.category,
        severity=report.severity,
        latitude=report.latitude,
        longitude=report.longitude,
        location_name=report.location_name,
        city=report.city,
        state=report.state,
        source="COMMUNITY",
        verification_status=report.verification_status,
        payload={"status": report.status, "is_verified": report.is_verified}
    )
    db.add(activity)
    await db.commit()

    schema_data = map_report_to_schema(report)

    # Broadcast real-time update
    await EventBroker.publish_event(
        event_type=activity_type,
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
    Automatically elevates report trust to VERIFIED_COMMUNITY when upvote threshold is reached.
    """
    res = await db.execute(select(IncidentReport).where(IncidentReport.id == report_id))
    report = res.scalars().first()
    if not report:
        raise HTTPException(status_code=404, detail="Community report not found.")

    v_type = payload.vote_type.upper()
    if v_type not in ["UPVOTE", "DOWNVOTE"]:
        raise HTTPException(status_code=400, detail="vote_type must be 'UPVOTE' or 'DOWNVOTE'.")

    # Check existing vote
    v_res = await db.execute(
        select(ReportVote).where(ReportVote.report_id == report_id, ReportVote.voter_id == payload.voter_id)
    )
    existing_vote = v_res.scalars().first()

    if existing_vote:
        if existing_vote.vote_type == v_type:
            # Already voted
            pass
        else:
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

    # Automatic Community Verification Elevation
    if (report.upvotes or 0) >= 3 and (report.upvotes or 0) > ((report.downvotes or 0) * 2):
        report.verification_status = "VERIFIED_COMMUNITY"
        report.is_verified = True

    report.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(report)

    schema_data = map_report_to_schema(report)

    # Broadcast update event
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
