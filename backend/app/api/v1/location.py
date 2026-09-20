"""
AEGIS UNIFIED DATA CORE - Geographic & Administrative Location API
/api/v1/location
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.providers.adapters.geographic import GeographicLocationProvider
from backend.app.cache.redis_client import CacheManager
from backend.app.api.deps import rate_limit_check

router = APIRouter(prefix="/location", tags=["Geographic & Location Services"])


class LocationSearchResult(BaseModel):
    name: str
    locality: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    country: str = "India"
    latitude: float
    longitude: float
    elevation: Optional[float] = 0.0
    timezone: str = "Asia/Kolkata"
    source: str = "AEGIS Geographic Registry"


class ReverseLocationResult(BaseModel):
    name: str
    locality: str
    district: str
    state: str
    country: str
    latitude: float
    longitude: float
    distance_to_centroid_km: float = 0.0
    elevation: float = 0.0
    timezone: str = "Asia/Kolkata"
    confidence: float = 1.0
    source: str = "AEGIS Geographic Registry"


@router.get("", response_model=ApiResponse[Dict[str, Any]], dependencies=[Depends(rate_limit_check)])
async def get_location_info(
    query: Optional[str] = Query(default=None, description="Search location name"),
    lat: Optional[float] = Query(default=None, ge=-90.0, le=90.0, description="Latitude for reverse geocoding"),
    lng: Optional[float] = Query(default=None, ge=-180.0, le=180.0, description="Longitude for reverse geocoding (lng)"),
    lon: Optional[float] = Query(default=None, ge=-180.0, le=180.0, description="Longitude for reverse geocoding (lon)"),
):
    """
    Unified location resolver: accepts either a text search query or coordinates.
    """
    provider = GeographicLocationProvider()
    longitude = lng if lng is not None else lon

    if query:
        cache_key = f"geo_search_{query.strip().lower()}"
        cached = await CacheManager.get(cache_key)
        if cached:
            return ApiResponse(
                success=True,
                data={"query": query, "results": cached},
                freshness=FreshnessMetadata(status="fresh", age_seconds=30),
                provenance=ProvenanceMetadata(
                    data_type="geographic_reference",
                    source_authority="Open-Meteo & AEGIS Centroid Registry",
                    processing_version="1.0.0"
                )
            )

        results = await provider.geocode(query, count=5)
        await CacheManager.set(cache_key, results, ttl_seconds=3600)
        return ApiResponse(
            success=True,
            data={"query": query, "results": results},
            freshness=FreshnessMetadata(status="fresh", age_seconds=5),
            provenance=ProvenanceMetadata(
                data_type="geographic_reference",
                source_authority="Open-Meteo & AEGIS Centroid Registry",
                processing_version="1.0.0"
            )
        )

    if lat is not None and longitude is not None:
        cache_key = f"geo_reverse_{lat:.3f}_{longitude:.3f}"
        cached = await CacheManager.get(cache_key)
        if cached:
            return ApiResponse(
                success=True,
                data=cached,
                freshness=FreshnessMetadata(status="fresh", age_seconds=30),
                provenance=ProvenanceMetadata(
                    data_type="geographic_reference",
                    source_authority="AEGIS Administrative Boundary Grid",
                    processing_version="1.0.0"
                )
            )

        resolved = await provider.reverse_geocode(lat, longitude)
        await CacheManager.set(cache_key, resolved, ttl_seconds=3600)
        return ApiResponse(
            success=True,
            data=resolved,
            freshness=FreshnessMetadata(status="fresh", age_seconds=5),
            provenance=ProvenanceMetadata(
                data_type="geographic_reference",
                source_authority="AEGIS Administrative Boundary Grid",
                processing_version="1.0.0"
            )
        )

    raise HTTPException(status_code=400, detail="Must provide either 'query' string or ('lat', 'lng'/'lon') coordinates.")


@router.get("/search", response_model=ApiResponse[List[LocationSearchResult]], dependencies=[Depends(rate_limit_check)])
async def search_location(
    query: str = Query(..., min_length=2, description="Place or city name"),
    limit: int = Query(default=5, ge=1, le=20)
):
    """
    Forward geocodes city, district, or landmark to geographic coordinates.
    """
    provider = GeographicLocationProvider()
    results = await provider.geocode(query, count=limit)
    return ApiResponse(
        success=True,
        data=[LocationSearchResult(**r) for r in results],
        freshness=FreshnessMetadata(status="fresh", age_seconds=5),
        provenance=ProvenanceMetadata(
            data_type="geographic_reference",
            source_authority="Open-Meteo & AEGIS Centroid Registry",
            processing_version="1.0.0"
        )
    )


@router.get("/reverse", response_model=ApiResponse[ReverseLocationResult], dependencies=[Depends(rate_limit_check)])
async def reverse_location(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lng: Optional[float] = Query(default=None, ge=-180.0, le=180.0, description="Longitude (lng)"),
    lon: Optional[float] = Query(default=None, ge=-180.0, le=180.0, description="Longitude (lon)")
):
    """
    Reverse geocodes latitude/longitude coordinates into administrative district, state, and elevation.
    """
    longitude = lng if lng is not None else lon
    if longitude is None:
        raise HTTPException(status_code=422, detail="Missing required longitude coordinate (provide 'lng' or 'lon').")

    provider = GeographicLocationProvider()
    resolved = await provider.reverse_geocode(lat, longitude)
    return ApiResponse(
        success=True,
        data=ReverseLocationResult(**resolved),
        freshness=FreshnessMetadata(status="fresh", age_seconds=5),
        provenance=ProvenanceMetadata(
            data_type="geographic_reference",
            source_authority="AEGIS Administrative Boundary Grid",
            processing_version="1.0.0"
        )
    )
