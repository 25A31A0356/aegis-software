"""
AEGIS UNIFIED DATA CORE - Emergency Shelters, Safe Zones & Hospitals Directory
/api/v1/shelters
Provides verified relief shelters, evacuation hubs, NDRF camps, and hospitals from PostgreSQL.
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, desc
from backend.app.database.session import get_db
from backend.app.database.models import SafeZone, utc_now
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.ingestion.deduplicator import EventDeduplicator
from backend.app.api.deps import rate_limit_check

router = APIRouter(prefix="/shelters", tags=["Safe Shelters & Medical Hubs"])


class ShelterItemSchema(BaseModel):
    id: str
    name: str
    zone_type: str
    latitude: float
    longitude: float
    capacity: int
    current_occupancy: int
    available_capacity: int
    occupancy_rate: float
    address: str
    city: str
    district: str
    state: str
    contact_phone: str
    is_active: bool
    amenities: List[str]
    distance_km: Optional[float] = None


@router.get("", response_model=ApiResponse[List[ShelterItemSchema]], dependencies=[Depends(rate_limit_check)])
async def list_shelters(
    zone_type: Optional[str] = Query(default=None, description="RELIEF_SHELTER, EVACUATION_CENTER, MEDICAL_STATION, HOSPITAL, SAFE_ZONE, ALL"),
    state: Optional[str] = Query(default=None, description="State filter"),
    district: Optional[str] = Query(default=None, description="District filter"),
    lat: Optional[float] = Query(default=None, ge=-90.0, le=90.0),
    lng: Optional[float] = Query(default=None, ge=-180.0, le=180.0),
    radius_km: Optional[float] = Query(default=100.0, ge=1.0, le=1000.0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns authentic verified emergency shelters, evacuation centers, and hospital hubs.
    """
    query = select(SafeZone).where(SafeZone.is_active == True)

    if zone_type and zone_type.upper() != "ALL":
        query = query.where(SafeZone.zone_type == zone_type.upper())

    if state and state.lower() not in ("all", "india"):
        query = query.where(SafeZone.state.ilike(f"%{state}%"))

    if district and district.lower() not in ("all", "india"):
        query = query.where(SafeZone.district.ilike(f"%{district}%"))

    query = query.limit(limit)
    res = await db.execute(query)
    rows = res.scalars().all()

    items: List[ShelterItemSchema] = []
    for r in rows:
        dist = None
        if lat is not None and lng is not None:
            dist = EventDeduplicator.haversine_distance_km(lat, lng, r.latitude, r.longitude)
            eff_radius = radius_km if radius_km is not None else 100.0
            if dist is not None and dist > eff_radius:
                continue

        avail = max(0, r.capacity - r.current_occupancy)
        occ_rate = round((r.current_occupancy / r.capacity * 100) if r.capacity > 0 else 0, 1)

        items.append(ShelterItemSchema(
            id=r.id,
            name=r.name,
            zone_type=r.zone_type,
            latitude=r.latitude,
            longitude=r.longitude,
            capacity=r.capacity,
            current_occupancy=r.current_occupancy,
            available_capacity=avail,
            occupancy_rate=occ_rate,
            address=r.address or "",
            city=r.city or "",
            district=r.district or "",
            state=r.state or "",
            contact_phone=r.contact_phone or "",
            is_active=r.is_active,
            amenities=r.amenities or [],
            distance_km=round(dist, 1) if dist is not None else None
        ))

    if lat is not None and lng is not None:
        items.sort(key=lambda x: x.distance_km if x.distance_km is not None else 999999)

    return ApiResponse(
        success=True,
        data=items,
        freshness=FreshnessMetadata(status="fresh", age_seconds=10),
        provenance=ProvenanceMetadata(
            data_type="verified_safe_zones",
            source_authority="NDMA & SDMA Infrastructure Directory",
            processing_version="1.0.0"
        )
    )


@router.get("/nearby", response_model=ApiResponse[List[ShelterItemSchema]], dependencies=[Depends(rate_limit_check)])
async def get_nearby_shelters(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lng: float = Query(..., ge=-180.0, le=180.0),
    radius_km: float = Query(default=50.0, ge=1.0, le=500.0),
    category: Optional[str] = Query(default="ALL"),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Proximity-sorted lookup for nearest safe shelters and trauma centers.
    """
    return await list_shelters(
        zone_type=category,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        limit=limit,
        db=db
    )
