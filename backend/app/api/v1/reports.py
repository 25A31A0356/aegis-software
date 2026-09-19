"""
AEGIS UNIFIED DATA CORE - Citizen Incident Reporting API
/api/v1/reports
Used by mobile app (https://github.com/25A31A0356/aegis-alert) and web dashboard
"""
from typing import Optional, List, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.database.session import get_db
from backend.app.database.models import IncidentReport
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.api.deps import rate_limit_check

router = APIRouter(prefix="/reports", tags=["Incident Reports"])


class IncidentCreateRequest(BaseModel):
    hazard_type: str = Field(..., description="FLOOD, EARTHQUAKE, FIRE, STORM, LANDSLIDE, ROAD_BLOCKED")
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5)
    severity: str = Field(default="medium", description="low, medium, high, critical")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    location_name: Optional[str] = Field(default="")
    city: Optional[str] = Field(default="")
    state: Optional[str] = Field(default="")
    media_urls: Optional[List[str]] = Field(default_factory=list)


class IncidentResponseSchema(BaseModel):
    id: str
    hazard_type: str
    title: str
    description: str
    severity: str
    latitude: float
    longitude: float
    location_name: Optional[str]
    city: Optional[str]
    state: Optional[str]
    media_urls: List[str]
    is_verified: bool
    verification_source: str
    created_at: str


@router.post("", response_model=ApiResponse[IncidentResponseSchema], dependencies=[Depends(rate_limit_check)])
async def create_incident_report(
    payload: IncidentCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Submit a citizen damage or ground-truth disaster report.
    """
    report = IncidentReport(
        hazard_type=payload.hazard_type.upper(),
        title=payload.title,
        description=payload.description,
        severity=payload.severity.lower(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        location_name=payload.location_name or "",
        city=payload.city or "",
        state=payload.state or "",
        media_urls=payload.media_urls or [],
        is_verified=False,
        verification_source="CITIZEN_SUBMISSION"
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return ApiResponse(
        success=True,
        data=IncidentResponseSchema(
            id=report.id,
            hazard_type=report.hazard_type,
            title=report.title,
            description=report.description,
            severity=report.severity,
            latitude=report.latitude,
            longitude=report.longitude,
            location_name=report.location_name,
            city=report.city,
            state=report.state,
            media_urls=report.media_urls or [],
            is_verified=report.is_verified,
            verification_source=report.verification_source,
            created_at=report.created_at.isoformat(),
        ),
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="AEGIS Crowdsourced Ground-Truth Network",
            processing_version="1.0.0"
        )
    )


@router.get("", response_model=ApiResponse[List[IncidentResponseSchema]])
async def list_incident_reports(
    hazard_type: Optional[str] = Query(default="ALL"),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """
    List verified and unverified citizen disaster reports.
    """
    query = select(IncidentReport).order_by(desc(IncidentReport.created_at)).limit(limit)
    if hazard_type and hazard_type != "ALL":
        query = query.where(IncidentReport.hazard_type == hazard_type.upper())

    res = await db.execute(query)
    rows = res.scalars().all()

    items = [
        IncidentResponseSchema(
            id=r.id,
            hazard_type=r.hazard_type,
            title=r.title,
            description=r.description,
            severity=r.severity,
            latitude=r.latitude,
            longitude=r.longitude,
            location_name=r.location_name,
            city=r.city,
            state=r.state,
            media_urls=r.media_urls or [],
            is_verified=r.is_verified,
            verification_source=r.verification_source,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]

    return ApiResponse(
        success=True,
        data=items,
        freshness=FreshnessMetadata(status="fresh", age_seconds=10),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="AEGIS Incident Triage Network",
            processing_version="1.0.0"
        )
    )
