"""
AEGIS UNIFIED DATA CORE - Emergency SOS Distress API
/api/v1/sos
Used by mobile client (https://github.com/25A31A0356/aegis-alert) and web dashboard
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.database.session import get_db
from backend.app.database.models import SOSSignal
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.api.deps import rate_limit_check

router = APIRouter(prefix="/sos", tags=["Emergency SOS Distress"])


class SOSCreateRequest(BaseModel):
    caller_name: str = Field(default="Citizen in Distress")
    caller_phone: str = Field(default="")
    emergency_type: str = Field(default="general", description="medical, flood_trapped, fire, building_collapse, cyclone_shelter, general")
    severity: str = Field(default="CRITICAL")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy_meters: Optional[float] = Field(default=10.0)
    address: Optional[str] = Field(default="")
    city: Optional[str] = Field(default="")
    state: Optional[str] = Field(default="")
    battery_percent: Optional[int] = Field(default=100, ge=0, le=100)
    medical_notes: Optional[str] = Field(default="")
    casualties_count: Optional[int] = Field(default=1, ge=1)
    device_id: Optional[str] = Field(default=None)


class SOSResponseSchema(BaseModel):
    id: str
    caller_name: str
    caller_phone_masked: str
    emergency_type: str
    severity: str
    status: str
    latitude: float
    longitude: float
    accuracy_meters: Optional[float]
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    battery_percent: Optional[int]
    medical_notes: Optional[str]
    casualties_count: int
    created_at: str
    updated_at: str


def _mask_phone(phone: str) -> str:
    if not phone or len(phone) < 4:
        return "PRIVATE"
    return f"{phone[:3]} ***** {phone[-2:]}" if len(phone) >= 7 else f"***{phone[-2:]}"


@router.post("", response_model=ApiResponse[SOSResponseSchema], dependencies=[Depends(rate_limit_check)])
async def create_sos_beacon(
    payload: SOSCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Submit an urgent SOS distress beacon from mobile or web client.
    """
    sos = SOSSignal(
        device_id=payload.device_id,
        caller_name=payload.caller_name,
        caller_phone=payload.caller_phone,
        emergency_type=payload.emergency_type.lower(),
        severity=payload.severity.upper(),
        status="PENDING_TRIAGE",
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_meters=payload.accuracy_meters,
        address=payload.address or "",
        city=payload.city or "",
        state=payload.state or "",
        battery_percent=payload.battery_percent,
        medical_notes=payload.medical_notes or "",
        casualties_count=payload.casualties_count or 1,
    )
    db.add(sos)
    await db.commit()
    await db.refresh(sos)

    return ApiResponse(
        success=True,
        data=SOSResponseSchema(
            id=sos.id,
            caller_name=sos.caller_name,
            caller_phone_masked=_mask_phone(sos.caller_phone),
            emergency_type=sos.emergency_type,
            severity=sos.severity,
            status=sos.status,
            latitude=sos.latitude,
            longitude=sos.longitude,
            accuracy_meters=sos.accuracy_meters,
            address=sos.address,
            city=sos.city,
            state=sos.state,
            battery_percent=sos.battery_percent,
            medical_notes=sos.medical_notes,
            casualties_count=sos.casualties_count,
            created_at=sos.created_at.isoformat(),
            updated_at=sos.updated_at.isoformat(),
        ),
        freshness=FreshnessMetadata(status="fresh", age_seconds=0),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="AEGIS Citizen Distress Beacon Gateway",
            processing_version="1.0.0"
        )
    )


@router.get("", response_model=ApiResponse[List[SOSResponseSchema]])
async def list_active_sos(
    status: Optional[str] = Query(default="ALL"),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """
    List active SOS distress beacons for SDRF command center and responders.
    """
    query = select(SOSSignal).order_by(desc(SOSSignal.created_at)).limit(limit)
    if status and status != "ALL":
        query = query.where(SOSSignal.status == status)

    res = await db.execute(query)
    rows = res.scalars().all()

    items = [
        SOSResponseSchema(
            id=s.id,
            caller_name=s.caller_name,
            caller_phone_masked=_mask_phone(s.caller_phone),
            emergency_type=s.emergency_type,
            severity=s.severity,
            status=s.status,
            latitude=s.latitude,
            longitude=s.longitude,
            accuracy_meters=s.accuracy_meters,
            address=s.address,
            city=s.city,
            state=s.state,
            battery_percent=s.battery_percent,
            medical_notes=s.medical_notes,
            casualties_count=s.casualties_count,
            created_at=s.created_at.isoformat() if s.created_at else "",
            updated_at=s.updated_at.isoformat() if s.updated_at else "",
        )
        for s in rows
    ]

    return ApiResponse(
        success=True,
        data=items,
        freshness=FreshnessMetadata(status="fresh", age_seconds=5),
        provenance=ProvenanceMetadata(
            data_type="official_observation",
            source_authority="AEGIS Emergency Response Dispatcher",
            processing_version="1.0.0"
        )
    )
