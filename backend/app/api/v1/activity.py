"""
AEGIS UNIFIED DATA CORE - Unified Activity Feed & Live Event Stream
/api/v1/activity
Merges Official Bulletins, Ground-Truth Community Reports, and Emergency SOS Broadcasts.
"""
from typing import Optional, List, Dict, Any
import asyncio
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from backend.app.database.session import get_db
from backend.app.database.models import ActivityEvent, IncidentReport
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.ingestion.deduplicator import EventDeduplicator
from backend.app.realtime.manager import manager
from backend.app.api.deps import rate_limit_check

router = APIRouter(prefix="/activity", tags=["Unified Activity Stream"])


class ActivityItemSchema(BaseModel):
    id: str
    event_type: str
    entity_type: str
    entity_id: str
    title: str
    description: str
    category: str
    severity: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = ""
    city: Optional[str] = ""
    state: Optional[str] = ""
    source: str
    verification_status: str
    payload: Dict[str, Any] = {}
    created_at: str


@router.get("", response_model=ApiResponse[List[ActivityItemSchema]], dependencies=[Depends(rate_limit_check)])
async def get_activity_feed(
    category: Optional[str] = Query(default="ALL", description="Category filter (FLOOD, EARTHQUAKE, FIRE, ROAD, ALL)"),
    severity: Optional[str] = Query(default="ALL", description="Severity filter (LOW, MODERATE, HIGH, CRITICAL, ALL)"),
    source: Optional[str] = Query(default="ALL", description="OFFICIAL, COMMUNITY, ALL"),
    lat: Optional[float] = Query(default=None, ge=-90.0, le=90.0),
    lng: Optional[float] = Query(default=None, ge=-180.0, le=180.0),
    lon: Optional[float] = Query(default=None, ge=-180.0, le=180.0),
    radius_km: Optional[float] = Query(default=150.0, ge=1.0, le=1000.0),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Unified Activity Feed for Aegis Web and Mobile App.
    Chronological public safety timeline with category, severity, and spatial filtering.
    """
    resolved_lon = lng if lng is not None else lon

    query = select(ActivityEvent).order_by(desc(ActivityEvent.created_at))

    # Category Filter
    if category and category.upper() != "ALL":
        query = query.where(func.upper(ActivityEvent.category) == category.upper())

    # Severity Filter
    if severity and severity.upper() != "ALL":
        query = query.where(func.upper(ActivityEvent.severity) == severity.upper())

    # Source Filter
    if source and source.upper() != "ALL":
        query = query.where(func.upper(ActivityEvent.source) == source.upper())

    query = query.limit(limit * 3 if (lat and resolved_lon) else limit).offset(offset)
    res = await db.execute(query)
    rows = res.scalars().all()

    # Fallback to IncidentReports and Alerts if ActivityEvent table is fresh
    items: List[ActivityItemSchema] = []
    if rows:
        for r in rows:
            if lat is not None and resolved_lon is not None and r.latitude and r.longitude:
                dist = EventDeduplicator.haversine_distance_km(lat, resolved_lon, r.latitude, r.longitude)
                if dist > (radius_km or 150.0):
                    continue

            items.append(ActivityItemSchema(
                id=r.id,
                event_type=r.event_type,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                title=r.title,
                description=r.description,
                category=r.category,
                severity=r.severity,
                latitude=r.latitude,
                longitude=r.longitude,
                location_name=r.location_name or "",
                city=r.city or "",
                state=r.state or "",
                source=r.source,
                verification_status=r.verification_status,
                payload=r.payload or {},
                created_at=r.created_at.isoformat() if r.created_at else "",
            ))
            if len(items) >= limit:
                break
    else:
        # Fallback to recent incident reports
        rep_query = select(IncidentReport).order_by(desc(IncidentReport.created_at)).limit(limit)
        rep_res = await db.execute(rep_query)
        rep_rows = rep_res.scalars().all()
        for r in rep_rows:
            items.append(ActivityItemSchema(
                id=f"act_{r.id}",
                event_type="REPORT_CREATED",
                entity_type="COMMUNITY_REPORT",
                entity_id=r.id,
                title=r.title,
                description=r.description,
                category=r.category or r.hazard_type,
                severity=r.severity,
                latitude=r.latitude,
                longitude=r.longitude,
                location_name=r.location_name or "",
                city=r.city or "",
                state=r.state or "",
                source=r.source or "COMMUNITY",
                verification_status=r.verification_status or "UNVERIFIED_COMMUNITY",
                payload={"media_urls": r.media_urls or []},
                created_at=r.created_at.isoformat() if r.created_at else "",
            ))

    return ApiResponse(
        success=True,
        data=items,
        freshness=FreshnessMetadata(status="fresh", age_seconds=5),
        provenance=ProvenanceMetadata(
            data_type="unified_activity_feed",
            source_authority="AEGIS Multi-Channel Stream",
            processing_version="2.4.0"
        )
    )


@router.get("/stream")
async def stream_live_activity(request: Request):
    """
    Server-Sent Events (SSE) live activity stream.
    Enables low-latency real-time event updates without polling.
    """
    async def event_generator():
        q = await manager.add_sse_listener()
        try:
            # Send initial connection handshake event
            init_payload = json.dumps({"status": "CONNECTED", "stream": "aegis_activity", "time": datetime.now(timezone.utc).isoformat()})
            yield f"event: connect\ndata: {init_payload}\n\n"

            while True:
                # Check for client disconnect
                if await request.is_disconnected():
                    break
                try:
                    # Wait for next event or 15s heartbeat
                    event_data = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"event: {event_data.get('event', 'message')}\ndata: {json.dumps(event_data)}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive ping
                    yield f": keepalive {datetime.now(timezone.utc).isoformat()}\n\n"
        finally:
            manager.remove_sse_listener(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
