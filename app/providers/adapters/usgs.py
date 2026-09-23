"""
AEGIS UNIFIED DATA CORE - USGS Seismological Feed Adapter
Pulls authentic real-time earthquake feeds (GeoJSON) and maps them into AEGIS Seismological schema.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import uuid
from backend.app.providers.base import BaseProvider
from backend.app.schemas.unified import UnifiedObservation, GeoLocation


class USGSSeismologyProvider(BaseProvider):
    def __init__(
        self,
        name: str = "USGS Earthquake Hazards Program",
        base_url: str = "https://earthquake.usgs.gov",
        endpoint: str = "/earthquakes/feed/v1.0/summary/2.5_day.geojson",
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 15.0
    ):
        super().__init__(
            name=name,
            provider_code="usgs",
            base_url=base_url,
            endpoint=endpoint,
            api_key=api_key,
            headers=headers,
            params=params,
            timeout_seconds=timeout_seconds
        )

    def parse(self, raw_data: Any) -> List[Dict[str, Any]]:
        if not isinstance(raw_data, dict):
            return []
        features = raw_data.get("features", [])
        records = []
        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", [])
            if len(coords) < 2:
                continue
            
            records.append({
                "event_id": feat.get("id"),
                "longitude": float(coords[0]),
                "latitude": float(coords[1]),
                "depth_km": float(coords[2]) if len(coords) > 2 else 10.0,
                "magnitude": float(props.get("mag", 0.0)),
                "place": props.get("place", "Regional Seismological Station"),
                "time_ms": props.get("time"),
                "status": props.get("status", "reviewed"),
                "tsunami_flag": props.get("tsunami", 0),
                "significance": props.get("sig", 0),
            })
        return records

    def normalize(self, record: Dict[str, Any]) -> Optional[UnifiedObservation]:
        lat = record["latitude"]
        lng = record["longitude"]
        mag = record["magnitude"]
        depth = record["depth_km"]
        time_ms = record.get("time_ms")
        
        obs_time = datetime.fromtimestamp(time_ms / 1000.0, tz=timezone.utc) if time_ms else datetime.now(timezone.utc)

        # Risk and severity mapping
        severity = "minor"
        risk_level = "LOW"
        if mag >= 6.5:
            severity = "critical"
            risk_level = "EXTREME"
        elif mag >= 5.0:
            severity = "warning"
            risk_level = "HIGH"
        elif mag >= 3.8:
            severity = "moderate"
            risk_level = "MODERATE"

        return UnifiedObservation(
            id=str(uuid.uuid4()),
            source_record_id=f"USGS-EQ-{record['event_id']}",
            hazard_type="EARTHQUAKE",
            location=GeoLocation(
                latitude=lat,
                longitude=lng,
                city_name=record.get("place", "Epicenter")
            ),
            observed_at=obs_time,
            received_at=datetime.now(timezone.utc),
            severity=severity,
            risk_level=risk_level,
            confidence=0.98,
            data_type="official_observation",
            source_authority="USGS National Seismological Center",
            processing_version="1.0.0",
            measurements={
                "magnitude": mag,
                "depth_km": depth,
                "tsunami_flag": record.get("tsunami_flag", 0),
                "significance_index": record.get("significance", 0)
            },
            metadata={
                "place_description": record.get("place"),
                "network_status": record.get("status")
            }
        )

    def validate(self, normalized: UnifiedObservation) -> Tuple[bool, Optional[str]]:
        if not (-90.0 <= normalized.location.latitude <= 90.0):
            return False, f"Invalid latitude: {normalized.location.latitude}"
        if not (-180.0 <= normalized.location.longitude <= 180.0):
            return False, f"Invalid longitude: {normalized.location.longitude}"
        mag = normalized.measurements.get("magnitude", 0.0)
        if not (0.0 <= mag <= 10.0):
            return False, f"Impossible earthquake magnitude: {mag}"
        return True, None
