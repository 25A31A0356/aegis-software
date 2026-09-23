"""
AEGIS UNIFIED DATA CORE - Emergency Facilities & Response Infrastructure API
/api/v1/facilities
Authoritative registry of Hospitals, Fire Stations, Police Posts, NDRF Bases, and Relief Shelters.
Directly queries PostgreSQL/PostGIS. Zero synthetic facilities.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, or_

from backend.app.database.session import get_db
from backend.app.database.models import EmergencyFacility, User, utc_now
from backend.app.schemas.common import ApiResponse, ProvenanceMetadata
from backend.app.api.deps import (
    get_current_active_user,
    require_operator_or_above,
    require_official_or_above,
    rate_limit_check
)
from backend.app.ingestion.deduplicator import EventDeduplicator

router = APIRouter(prefix="/facilities", tags=["Emergency Facilities & Infrastructure"])


class FacilityCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    facility_type: str = Field(..., description="HOSPITAL, FIRE_STATION, POLICE_STATION, RELIEF_CAMP, NDRF_BASE, DISASTER_HQ")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    address: Optional[str] = ""
    city: Optional[str] = ""
    district: Optional[str] = ""
    state: Optional[str] = ""
    contact_phone: Optional[str] = ""
    capacity: int = Field(100, ge=0)
    current_occupancy: int = Field(0, ge=0)
    operational_status: str = Field("OPERATIONAL", description="OPERATIONAL, COMPROMISED, EVACUATED, OFFLINE")
    amenities: List[str] = Field(default_factory=list)
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class FacilityUpdateRequest(BaseModel):
    name: Optional[str] = None
    operational_status: Optional[str] = None
    capacity: Optional[int] = None
    current_occupancy: Optional[int] = None
    contact_phone: Optional[str] = None
    amenities: Optional[List[str]] = None
    is_active: Optional[bool] = None
    metadata_json: Optional[Dict[str, Any]] = None


def serialize_facility(f: EmergencyFacility, distance_km: Optional[float] = None) -> Dict[str, Any]:
    res = {
        "id": f.id,
        "name": f.name,
        "facility_type": f.facility_type,
        "latitude": f.latitude,
        "longitude": f.longitude,
        "address": f.address,
        "city": f.city,
        "district": f.district,
        "state": f.state,
        "contact_phone": f.contact_phone,
        "capacity": f.capacity,
        "current_occupancy": f.current_occupancy,
        "available_capacity": max(0, f.capacity - f.current_occupancy),
        "operational_status": f.operational_status,
        "amenities": f.amenities or [],
        "is_active": f.is_active,
        "metadata": f.metadata_json or {},
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "updated_at": f.updated_at.isoformat() if f.updated_at else None
    }
    if distance_km is not None:
        res["distance_km"] = round(distance_km, 2)
    return res


@router.get("", response_model=ApiResponse[List[Dict[str, Any]]], dependencies=[Depends(rate_limit_check)])
async def list_emergency_facilities(
    facility_type: Optional[str] = Query(None, description="HOSPITAL, FIRE_STATION, POLICE_STATION, RELIEF_CAMP, NDRF_BASE, DISASTER_HQ"),
    operational_status: Optional[str] = Query(None, description="OPERATIONAL, COMPROMISED, EVACUATED, OFFLINE"),
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    min_lat: Optional[float] = Query(None, ge=-90.0, le=90.0),
    max_lat: Optional[float] = Query(None, ge=-90.0, le=90.0),
    min_lng: Optional[float] = Query(None, ge=-180.0, le=180.0),
    max_lng: Optional[float] = Query(None, ge=-180.0, le=180.0),
    lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="User/Incident latitude for proximity"),
    lng: Optional[float] = Query(None, ge=-180.0, le=180.0, description="User/Incident longitude for proximity"),
    radius_km: Optional[float] = Query(50.0, ge=1.0, le=1000.0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    """
    Queries verified emergency facilities with bounding-box or radial proximity filters.
    """
    stmt = select(EmergencyFacility).where(EmergencyFacility.is_active == True)

    if facility_type and facility_type.upper() != "ALL":
        stmt = stmt.where(EmergencyFacility.facility_type == facility_type.upper())
    if operational_status and operational_status.upper() != "ALL":
        stmt = stmt.where(EmergencyFacility.operational_status == operational_status.upper())
    if state:
        stmt = stmt.where(EmergencyFacility.state.ilike(f"%{state}%"))
    if district:
        stmt = stmt.where(EmergencyFacility.district.ilike(f"%{district}%"))

    # Bounding Box Filter
    if min_lat is not None and max_lat is not None and min_lng is not None and max_lng is not None:
        stmt = stmt.where(
            and_(
                EmergencyFacility.latitude >= min_lat,
                EmergencyFacility.latitude <= max_lat,
                EmergencyFacility.longitude >= min_lng,
                EmergencyFacility.longitude <= max_lng
            )
        )

    res = await db.execute(stmt.limit(limit * 2))
    raw_facilities = res.scalars().all()

    # Radius Filter & Distance sorting if lat/lng supplied
    facilities_with_dist = []
    for f in raw_facilities:
        if lat is not None and lng is not None:
            dist = EventDeduplicator.haversine_distance_km(lat, lng, f.latitude, f.longitude)
            if dist <= (radius_km or 50.0):
                facilities_with_dist.append((f, dist))
        else:
            facilities_with_dist.append((f, None))

    if lat is not None and lng is not None:
        facilities_with_dist.sort(key=lambda x: x[1] if x[1] is not None else float("inf"))

    output = [serialize_facility(f, dist) for f, dist in facilities_with_dist[:limit]]

    return ApiResponse(
        success=True,
        data=output,
        provenance=ProvenanceMetadata(
            data_type="emergency_facilities",
            source_authority="AEGIS Infrastructure & Facilities Registry",
            processing_version="2.0.0"
        )
    )


@router.get("/{facility_id}", response_model=ApiResponse[Dict[str, Any]], dependencies=[Depends(rate_limit_check)])
async def get_emergency_facility(
    facility_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches detailed operational metadata for a single emergency facility.
    """
    res = await db.execute(select(EmergencyFacility).where(EmergencyFacility.id == facility_id))
    fac = res.scalar_one_or_none()
    if not fac:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emergency facility '{facility_id}' not found."
        )

    return ApiResponse(
        success=True,
        data=serialize_facility(fac),
        provenance=ProvenanceMetadata(
            data_type="emergency_facility_detail",
            source_authority="AEGIS Infrastructure & Facilities Registry",
            processing_version="2.0.0"
        )
    )


@router.post("", response_model=ApiResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED)
async def create_emergency_facility(
    payload: FacilityCreateRequest,
    current_user: User = Depends(require_operator_or_above),
    db: AsyncSession = Depends(get_db)
):
    """
    Operator/Official endpoint to register new critical emergency infrastructure.
    """
    fac = EmergencyFacility(
        name=payload.name,
        facility_type=payload.facility_type.upper(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        address=payload.address or "",
        city=payload.city or "",
        district=payload.district or "",
        state=payload.state or "",
        contact_phone=payload.contact_phone or "",
        capacity=payload.capacity,
        current_occupancy=payload.current_occupancy,
        operational_status=payload.operational_status.upper(),
        amenities=payload.amenities,
        is_active=True,
        metadata_json=payload.metadata_json,
        created_at=utc_now(),
        updated_at=utc_now()
    )
    db.add(fac)
    await db.commit()
    await db.refresh(fac)

    return ApiResponse(
        success=True,
        data=serialize_facility(fac),
        provenance=ProvenanceMetadata(
            data_type="emergency_facility_created",
            source_authority="AEGIS Operator Infrastructure Management",
            processing_version="2.0.0"
        )
    )


@router.patch("/{facility_id}", response_model=ApiResponse[Dict[str, Any]])
async def update_emergency_facility(
    facility_id: str,
    payload: FacilityUpdateRequest,
    current_user: User = Depends(require_operator_or_above),
    db: AsyncSession = Depends(get_db)
):
    """
    Operator/Official endpoint to update operational status, capacity, and occupancy.
    """
    res = await db.execute(select(EmergencyFacility).where(EmergencyFacility.id == facility_id))
    fac = res.scalar_one_or_none()
    if not fac:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emergency facility '{facility_id}' not found."
        )

    if payload.name is not None:
        fac.name = payload.name
    if payload.operational_status is not None:
        fac.operational_status = payload.operational_status.upper()
    if payload.capacity is not None:
        fac.capacity = payload.capacity
    if payload.current_occupancy is not None:
        fac.current_occupancy = payload.current_occupancy
    if payload.contact_phone is not None:
        fac.contact_phone = payload.contact_phone
    if payload.amenities is not None:
        fac.amenities = payload.amenities
    if payload.is_active is not None:
        fac.is_active = payload.is_active
    if payload.metadata_json is not None:
        fac.metadata_json = payload.metadata_json

    fac.updated_at = utc_now()
    await db.commit()
    await db.refresh(fac)

    return ApiResponse(
        success=True,
        data=serialize_facility(fac),
        provenance=ProvenanceMetadata(
            data_type="emergency_facility_updated",
            source_authority="AEGIS Operator Infrastructure Management",
            processing_version="2.0.0"
        )
    )


@router.delete("/{facility_id}", response_model=ApiResponse[Dict[str, Any]])
async def delete_emergency_facility(
    facility_id: str,
    current_user: User = Depends(require_official_or_above),
    db: AsyncSession = Depends(get_db)
):
    """
    Official/Admin endpoint to deactivate an emergency facility.
    """
    res = await db.execute(select(EmergencyFacility).where(EmergencyFacility.id == facility_id))
    fac = res.scalar_one_or_none()
    if not fac:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emergency facility '{facility_id}' not found."
        )

    fac.is_active = False
    fac.operational_status = "OFFLINE"
    fac.updated_at = utc_now()
    await db.commit()

    return ApiResponse(
        success=True,
        data={"id": facility_id, "deleted": True, "status": "OFFLINE"},
        provenance=ProvenanceMetadata(
            data_type="emergency_facility_deleted",
            source_authority="AEGIS Official Command Management",
            processing_version="2.0.0"
        )
    )
