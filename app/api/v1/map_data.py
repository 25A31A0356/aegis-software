"""
AEGIS UNIFIED DATA CORE - Geospatial Map Data & GIS Layers API
/api/v1/map-data
Powers Interactive Maps for Aegis Web (MapLibre / Leaflet) and Aegis App (React Native Maps / Mapbox).
Authoritative operational state directly from PostgreSQL/PostGIS. Zero synthetic markers.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, or_
from backend.app.database.session import get_db
from backend.app.database.models import (
    NormalizedObservation, AlertRecord, IncidentReport,
    SOSSignal, SOSAssignment, SOSLocationUpdate, UserPreference,
    User, SafeZone, SafeEvent, EmergencyFacility, utc_now
)
from backend.app.schemas.common import ApiResponse, FreshnessMetadata, ProvenanceMetadata
from backend.app.ingestion.deduplicator import EventDeduplicator
from backend.app.api.deps import rate_limit_check

router = APIRouter(prefix="/map-data", tags=["Geospatial Map Layers"])


class GeoJSONGeometry(BaseModel):
    type: str = "Point"
    coordinates: List[float]  # [longitude, latitude]


class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    id: str
    geometry: GeoJSONGeometry
    properties: Dict[str, Any]


class ClusterSummary(BaseModel):
    total_features: int
    cluster_count: int
    clusters: List[Dict[str, Any]] = []


class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature]
    layer_summary: Dict[str, int]
    clustering: Optional[ClusterSummary] = None
    generated_at: str


@router.get("", response_model=ApiResponse[GeoJSONFeatureCollection], dependencies=[Depends(rate_limit_check)])
async def get_unified_map_data(
    layers: Optional[str] = Query(default="all", description="Comma-separated layers: hazards,reports,sos_beacons,responders,shelters,facilities,road_hazards,safe_events,all"),
    category: Optional[str] = Query(default="ALL", description="Category / hazard type filter"),
    status: Optional[str] = Query(default=None, description="Status filter (e.g. TRIGGERED, RESPONDER_ASSIGNED, RESPONDER_EN_ROUTE, ON_SITE, ACTIVE, etc.)"),
    severity: Optional[str] = Query(default=None, description="Severity filter (e.g. CRITICAL, HIGH, MODERATE, LOW)"),
    bbox: Optional[str] = Query(default=None, description="Bounding box: minLon,minLat,maxLon,maxLat"),
    lat: Optional[float] = Query(default=None, ge=-90.0, le=90.0, description="Center latitude for proximity search"),
    lng: Optional[float] = Query(default=None, ge=-180.0, le=180.0, description="Center longitude for proximity search"),
    lon: Optional[float] = Query(default=None, ge=-180.0, le=180.0, description="Alias for lng"),
    radius_km: Optional[float] = Query(default=200.0, ge=1.0, le=2000.0, description="Radius in kilometers"),
    cluster: Optional[bool] = Query(default=False, description="Enable server-side grid clustering summary"),
    db: AsyncSession = Depends(get_db)
):
    """
    Unified Geospatial Map Data endpoint returning authoritative GeoJSON FeatureCollections.
    Single authoritative map data layer for both Web Portal and Mobile App.
    Consumes PostgreSQL/PostGIS database records directly. Never generates synthetic markers.
    """
    resolved_lon = lng if lng is not None else lon
    req_layers = [l.strip().lower() for l in layers.split(",")] if layers else ["all"]
    if "sos" in req_layers and "sos_beacons" not in req_layers:
        req_layers.append("sos_beacons")
    include_all = "all" in req_layers

    # Parse Bounding Box if provided
    bbox_parsed = None
    if bbox:
        try:
            parts = [float(p.strip()) for p in bbox.split(",")]
            if len(parts) == 4:
                bbox_parsed = {"min_lon": parts[0], "min_lat": parts[1], "max_lon": parts[2], "max_lat": parts[3]}
        except Exception:
            pass

    def in_bounds(latitude: float, longitude: float) -> bool:
        if latitude is None or longitude is None:
            return False
        if bbox_parsed:
            return (
                bbox_parsed["min_lat"] <= latitude <= bbox_parsed["max_lat"] and
                bbox_parsed["min_lon"] <= longitude <= bbox_parsed["max_lon"]
            )
        if lat is not None and resolved_lon is not None:
            dist = EventDeduplicator.haversine_distance_km(lat, resolved_lon, latitude, longitude)
            return dist <= (radius_km or 200.0)
        return True

    def matches_severity(item_severity: Optional[str]) -> bool:
        if not severity or severity.upper() == "ALL":
            return True
        if not item_severity:
            return False
        return item_severity.upper() == severity.upper()

    def matches_status(item_status: Optional[str]) -> bool:
        if not status or status.upper() == "ALL":
            return True
        if not item_status:
            return False
        allowed = [s.strip().upper() for s in status.split(",")]
        return item_status.upper() in allowed

    def matches_category(item_cat: Optional[str]) -> bool:
        if not category or category.upper() == "ALL":
            return True
        if not item_cat:
            return False
        return category.upper() in item_cat.upper()

    features: List[GeoJSONFeature] = []
    layer_counts: Dict[str, int] = {
        "hazards": 0,
        "reports": 0,
        "sos_beacons": 0,
        "responders": 0,
        "shelters": 0,
        "road_hazards": 0,
        "safe_events": 0,
        "facilities": 0
    }
    now = utc_now()

    # 1. LAYER: Official Active Hazards & Disaster Alerts
    if include_all or "hazards" in req_layers:
        haz_query = select(NormalizedObservation).order_by(desc(NormalizedObservation.observed_at)).limit(150)
        haz_res = await db.execute(haz_query)
        for h in haz_res.scalars().all():
            if in_bounds(h.latitude, h.longitude):
                if matches_severity(h.severity) and matches_category(h.hazard_type):
                    feat = GeoJSONFeature(
                        id=f"haz_{h.id}",
                        geometry=GeoJSONGeometry(type="Point", coordinates=[h.longitude, h.latitude]),
                        properties={
                            "layer": "hazards",
                            "entity_id": h.id,
                            "title": f"Official {h.hazard_type.capitalize()} Observation",
                            "description": f"Severity: {h.severity}. Source: {h.source_authority}",
                            "category": h.hazard_type,
                            "severity": (h.severity or "MODERATE").upper(),
                            "source": "OFFICIAL",
                            "source_authority": h.source_authority or "IMD/CWC/INCOIS",
                            "verification_status": "OFFICIAL",
                            "is_official": True,
                            "location_name": h.location_name or "",
                            "district": h.district_name or h.location_name or "",
                            "state": h.state_name or "",
                            "observed_at": h.observed_at.isoformat() if h.observed_at else "",
                            "icon": f"hazard_{h.hazard_type.lower()}"
                        }
                    )
                    features.append(feat)
                    layer_counts["hazards"] += 1

        alert_query = select(AlertRecord).where(AlertRecord.status.in_(["ACTIVE", "TRIGGERED", "ESCALATED"])).order_by(desc(AlertRecord.created_at)).limit(50)
        alert_res = await db.execute(alert_query)
        for a in alert_res.scalars().all():
            if in_bounds(a.latitude, a.longitude):
                if matches_severity(a.severity) and matches_category(a.hazard_type):
                    features.append(GeoJSONFeature(
                        id=f"alert_{a.id}",
                        geometry=GeoJSONGeometry(type="Point", coordinates=[a.longitude, a.latitude]),
                        properties={
                            "layer": "hazards",
                            "entity_id": a.id,
                            "title": a.title or f"Alert: {a.hazard_type}",
                            "description": a.description or a.instructions or "",
                            "category": a.hazard_type,
                            "severity": (a.severity or "HIGH").upper(),
                            "status": a.status,
                            "source": "COMMAND_CENTER",
                            "source_authority": a.source_authority or "SDMA/NDMA",
                            "verification_status": "OFFICIAL_ALERT",
                            "is_official": True,
                            "district": a.district_name or "",
                            "state": a.state_name or "",
                            "created_at": a.created_at.isoformat() if a.created_at else "",
                            "icon": "alert_broadcast"
                        }
                    ))
                    layer_counts["hazards"] += 1

    # 2. LAYER: Community Reports & Road Hazards
    if include_all or "reports" in req_layers or "road_hazards" in req_layers:
        rep_query = select(IncidentReport).where(IncidentReport.status == "ACTIVE").order_by(desc(IncidentReport.created_at)).limit(150)
        rep_res = await db.execute(rep_query)
        for r in rep_res.scalars().all():
            if in_bounds(r.latitude, r.longitude):
                if matches_severity(r.severity) and matches_category(r.category or r.hazard_type) and matches_status(r.status):
                    is_road = (r.category or "").upper() in ["BLOCKED_ROAD", "FALLEN_TREE", "LANDSLIDE", "DAMAGED_INFRASTRUCTURE", "WATERLOGGING"]
                    layer_name = "road_hazards" if is_road and ("road_hazards" in req_layers and not include_all) else "reports"
                    
                    feat = GeoJSONFeature(
                        id=f"rep_{r.id}",
                        geometry=GeoJSONGeometry(type="Point", coordinates=[r.longitude, r.latitude]),
                        properties={
                            "layer": layer_name,
                            "entity_id": r.id,
                            "title": r.title,
                            "description": r.description,
                            "category": r.category or r.hazard_type,
                            "severity": (r.severity or "MODERATE").upper(),
                            "status": r.status,
                            "source": "COMMUNITY",
                            "verification_status": r.verification_status,
                            "is_verified": r.is_verified,
                            "upvotes": r.upvotes or 0,
                            "downvotes": r.downvotes or 0,
                            "media_count": len(r.media_urls or []),
                            "location_name": r.location_name or "",
                            "city": r.city or "",
                            "state": r.state or "",
                            "created_at": r.created_at.isoformat() if r.created_at else "",
                            "icon": f"community_{(r.category or 'hazard').lower()}"
                        }
                    )
                    features.append(feat)
                    if is_road:
                        layer_counts["road_hazards"] += 1
                    else:
                        layer_counts["reports"] += 1

    # 3. LAYER: SOS Distress Beacons (Authoritative Database State)
    if include_all or "sos_beacons" in req_layers or "sos" in req_layers:
        active_sos_states = [
            "TRIGGERED", "ACKNOWLEDGED", "RESPONDER_MATCHING", "RESPONDER_ASSIGNED",
            "RESPONDER_EN_ROUTE", "ON_SITE", "PENDING", "MATCHING", "OFFERED",
            "ACCEPTED", "PENDING_TRIAGE", "DISPATCHED", "RESPONDER_ON_SCENE"
        ]
        sos_query = select(SOSSignal).where(SOSSignal.status.in_(active_sos_states)).order_by(desc(SOSSignal.created_at)).limit(100)
        sos_res = await db.execute(sos_query)
        for s in sos_res.scalars().all():
            if in_bounds(s.latitude, s.longitude):
                if matches_severity(s.severity) and matches_status(s.status) and matches_category(s.emergency_type):
                    feat = GeoJSONFeature(
                        id=f"sos_{s.id}",
                        geometry=GeoJSONGeometry(type="Point", coordinates=[s.longitude, s.latitude]),
                        properties={
                            "layer": "sos_beacons",
                            "entity_id": s.id,
                            "sos_id": s.id,
                            "title": f"Emergency SOS: {s.emergency_type.replace('_', ' ').title()}",
                            "description": f"Distress status: {s.status}. Casualties: {s.casualties_count}",
                            "category": "EMERGENCY_SOS",
                            "emergency_type": s.emergency_type,
                            "severity": (s.severity or "CRITICAL").upper(),
                            "status": s.status,
                            "source": "CITIZEN_SOS",
                            "caller_name": s.caller_name or "Citizen in Distress",
                            "casualties_count": s.casualties_count,
                            "battery_percent": s.battery_percent,
                            "accuracy_meters": s.accuracy_meters,
                            "city": s.city or "",
                            "district": s.district or "",
                            "state": s.state or "",
                            "last_location_update": s.last_location_update.isoformat() if s.last_location_update else (s.created_at.isoformat() if s.created_at else ""),
                            "created_at": s.created_at.isoformat() if s.created_at else "",
                            "icon": "emergency_beacon"
                        }
                    )
                    features.append(feat)
                    layer_counts["sos_beacons"] += 1

    # 4. LAYER: Responders (Live Telemetry & Last Known Verified GPS)
    if include_all or "responders" in req_layers:
        seen_responder_ids = set()

        # A. Query active assignments
        assign_query = select(SOSAssignment, User).join(
            User, User.id == SOSAssignment.responder_user_id, isouter=True
        ).where(SOSAssignment.status == "ACTIVE")
        assign_res = await db.execute(assign_query)
        for assign, user in assign_res.all():
            r_lat = assign.last_responder_lat
            r_lon = assign.last_responder_lon
            r_update = assign.last_responder_update

            if r_lat is None or r_lon is None:
                pref_res = await db.execute(select(UserPreference).where(UserPreference.user_id == assign.responder_user_id))
                pref = pref_res.scalars().first()
                if pref and pref.last_known_lat is not None and pref.last_known_lng is not None:
                    r_lat = pref.last_known_lat
                    r_lon = pref.last_known_lng
                    r_update = pref.last_location_time

            if r_lat is not None and r_lon is not None and in_bounds(r_lat, r_lon):
                is_live = False
                if r_update:
                    up_time = r_update if r_update.tzinfo else r_update.replace(tzinfo=timezone.utc)
                    is_live = (now - up_time).total_seconds() <= 300

                seen_responder_ids.add(assign.responder_user_id)
                features.append(GeoJSONFeature(
                    id=f"responder_{assign.responder_user_id}",
                    geometry=GeoJSONGeometry(type="Point", coordinates=[r_lon, r_lat]),
                    properties={
                        "layer": "responders",
                        "entity_id": assign.responder_user_id,
                        "responder_id": assign.responder_user_id,
                        "sos_id": assign.sos_id,
                        "name": (user.full_name if user and user.full_name else f"Responder {assign.responder_user_id[:6]}"),
                        "role": user.role if user else "responder",
                        "status": "DISPATCHED_EN_ROUTE",
                        "assignment_status": assign.status,
                        "category": "RESPONDER",
                        "severity": "LOW",
                        "is_live": is_live,
                        "last_location_time": r_update.isoformat() if r_update else "",
                        "eta_seconds": assign.eta_seconds or 0,
                        "distance_meters": assign.distance_meters or 0.0,
                        "icon": "responder_unit"
                    }
                ))
                layer_counts["responders"] += 1

        # B. Query available standby responders from UserPreference
        pref_query = select(UserPreference, User).join(
            User, User.id == UserPreference.user_id, isouter=True
        ).where(
            UserPreference.is_responder_opted_in == True,
            UserPreference.is_available == True,
            UserPreference.last_known_lat != None,
            UserPreference.last_known_lng != None
        ).limit(100)
        pref_res = await db.execute(pref_query)
        for pref, user in pref_res.all():
            if pref.user_id not in seen_responder_ids and in_bounds(pref.last_known_lat, pref.last_known_lng):
                is_live = False
                if pref.last_location_time:
                    up_time = pref.last_location_time if pref.last_location_time.tzinfo else pref.last_location_time.replace(tzinfo=timezone.utc)
                    is_live = (now - up_time).total_seconds() <= 300

                seen_responder_ids.add(pref.user_id)
                features.append(GeoJSONFeature(
                    id=f"responder_standby_{pref.user_id}",
                    geometry=GeoJSONGeometry(type="Point", coordinates=[pref.last_known_lng, pref.last_known_lat]),
                    properties={
                        "layer": "responders",
                        "entity_id": pref.user_id,
                        "responder_id": pref.user_id,
                        "sos_id": None,
                        "name": (user.full_name if user and user.full_name else f"Volunteer {pref.user_id[:6]}"),
                        "role": user.role if user else "volunteer_responder",
                        "status": "AVAILABLE_STANDBY",
                        "assignment_status": "NONE",
                        "category": "RESPONDER",
                        "severity": "LOW",
                        "is_live": is_live,
                        "last_location_time": pref.last_location_time.isoformat() if pref.last_location_time else "",
                        "icon": "responder_standby"
                    }
                ))
                layer_counts["responders"] += 1

    # 5. LAYER: Safe Zones & Relief Shelters (Strictly DB Records)
    if include_all or "shelters" in req_layers:
        safe_query = select(SafeZone).where(SafeZone.is_active == True).limit(100)
        safe_res = await db.execute(safe_query)
        safe_rows = safe_res.scalars().all()
        for s in safe_rows:
            if in_bounds(s.latitude, s.longitude):
                features.append(GeoJSONFeature(
                    id=f"shelter_{s.id}",
                    geometry=GeoJSONGeometry(type="Point", coordinates=[s.longitude, s.latitude]),
                    properties={
                        "layer": "shelters",
                        "entity_id": s.id,
                        "name": s.name,
                        "title": s.name,
                        "category": "SHELTER",
                        "severity": "LOW",
                        "source": "OFFICIAL",
                        "capacity": s.capacity,
                        "amenities": s.amenities or ["FOOD", "WATER", "MEDICAL"],
                        "city": s.city or "",
                        "district": s.district or s.city or "",
                        "state": s.state or "",
                        "icon": "shelter_hub"
                    }
                ))
                layer_counts["shelters"] += 1

    # 6. LAYER: Citizen Safe Declarations ("I AM SAFE")
    if include_all or "safe_events" in req_layers:
        safe_ev_query = select(SafeEvent).order_by(desc(SafeEvent.created_at)).limit(50)
        safe_ev_res = await db.execute(safe_ev_query)
        for se in safe_ev_res.scalars().all():
            if in_bounds(se.latitude, se.longitude):
                features.append(GeoJSONFeature(
                    id=f"safe_{se.id}",
                    geometry=GeoJSONGeometry(type="Point", coordinates=[se.longitude, se.latitude]),
                    properties={
                        "layer": "safe_events",
                        "entity_id": se.id,
                        "title": f"Citizen Safe: {se.user_name}",
                        "description": se.message or "I am safe and out of danger.",
                        "category": "SAFE_DECLARATION",
                        "severity": "LOW",
                        "status": se.status,
                        "source": "CITIZEN",
                        "verification_status": "VERIFIED",
                        "location_name": se.location_name or "",
                        "district": se.district or "",
                        "state": se.state or "",
                        "created_at": se.created_at.isoformat() if se.created_at else "",
                        "icon": "citizen_safe"
                    }
                ))
                layer_counts["safe_events"] += 1


    # 7. LAYER: Emergency Facilities & Critical Infrastructure
    if include_all or "facilities" in req_layers:
        fac_query = select(EmergencyFacility).where(EmergencyFacility.is_active == True).limit(150)
        fac_res = await db.execute(fac_query)
        for f in fac_res.scalars().all():
            if in_bounds(f.latitude, f.longitude):
                features.append(GeoJSONFeature(
                    id=f"facility_{f.id}",
                    geometry=GeoJSONGeometry(type="Point", coordinates=[f.longitude, f.latitude]),
                    properties={
                        "layer": "facilities",
                        "entity_id": f.id,
                        "name": f.name,
                        "title": f.name,
                        "facility_type": f.facility_type,
                        "category": f.facility_type,
                        "severity": "LOW",
                        "operational_status": f.operational_status,
                        "capacity": f.capacity,
                        "current_occupancy": f.current_occupancy,
                        "amenities": f.amenities or [],
                        "contact_phone": f.contact_phone or "",
                        "city": f.city or "",
                        "district": f.district or "",
                        "state": f.state or "",
                        "icon": f"facility_{f.facility_type.lower()}"
                    }
                ))
                layer_counts["facilities"] = layer_counts.get("facilities", 0) + 1

    # Server-Side Grid Clustering Summary if requested
    clustering_summary = None
    if cluster and features:
        grid: Dict[str, Dict[str, Any]] = {}
        for feat in features:
            lon_cell = round(feat.geometry.coordinates[0] * 2) / 2
            lat_cell = round(feat.geometry.coordinates[1] * 2) / 2
            cell_key = f"{lat_cell}:{lon_cell}"
            if cell_key not in grid:
                grid[cell_key] = {
                    "centroid": [lon_cell, lat_cell],
                    "count": 0,
                    "layer_breakdown": {}
                }
            grid[cell_key]["count"] += 1
            lyr = feat.properties.get("layer", "unknown")
            grid[cell_key]["layer_breakdown"][lyr] = grid[cell_key]["layer_breakdown"].get(lyr, 0) + 1

        cluster_list = [
            {
                "grid_id": k,
                "coordinates": v["centroid"],
                "total_items": v["count"],
                "layers": v["layer_breakdown"]
            }
            for k, v in grid.items()
        ]
        clustering_summary = ClusterSummary(
            total_features=len(features),
            cluster_count=len(cluster_list),
            clusters=cluster_list
        )

    return ApiResponse(
        success=True,
        data=GeoJSONFeatureCollection(
            type="FeatureCollection",
            features=features,
            layer_summary=layer_counts,
            clustering=clustering_summary,
            generated_at=datetime.now(timezone.utc).isoformat()
        ),
        freshness=FreshnessMetadata(status="fresh", age_seconds=1),
        provenance=ProvenanceMetadata(
            data_type="geospatial_feature_collection",
            source_authority="AEGIS Central GIS Engine",
            processing_version="2.5.0"
        )
    )
