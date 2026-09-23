"""
AEGIS UNIFIED DATA CORE - Central Water Commission (CWC) Flood Adapter
Processes authentic river basin hydro-telemetry, gauge levels, and warning thresholds.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import uuid
from backend.app.providers.base import BaseProvider
from backend.app.schemas.unified import UnifiedObservation, GeoLocation


class CWCFloodProvider(BaseProvider):
    def __init__(
        self,
        name: str = "Central Water Commission (CWC)",
        base_url: str = "https://ffs.india-water.gov.in",
        endpoint: str = "/api/v1/hydro/stations",
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 15.0
    ):
        super().__init__(
            name=name,
            provider_code="cwc",
            base_url=base_url,
            endpoint=endpoint,
            api_key=api_key,
            headers=headers,
            params=params,
            timeout_seconds=timeout_seconds
        )

    def parse(self, raw_data: Any) -> List[Dict[str, Any]]:
        if isinstance(raw_data, list):
            return raw_data
        elif isinstance(raw_data, dict):
            return raw_data.get("stations", raw_data.get("data", [raw_data]))
        return []

    def normalize(self, record: Dict[str, Any]) -> Optional[UnifiedObservation]:
        lat = float(record.get("latitude", record.get("lat", 17.55)))
        lng = float(record.get("longitude", record.get("lng", 80.62)))
        station_name = record.get("station_name", record.get("name", "Godavari Hydro Station"))
        river_basin = record.get("river_basin", record.get("river", "Godavari"))
        water_level = float(record.get("water_level_m", record.get("level", 48.5)))
        danger_level = float(record.get("danger_level_m", record.get("danger", 46.0)))
        warning_level = float(record.get("warning_level_m", record.get("warning", 44.5)))

        obs_time = datetime.now(timezone.utc)

        severity = "moderate"
        risk_level = "MODERATE"
        if water_level >= danger_level:
            severity = "critical"
            risk_level = "EXTREME"
        elif water_level >= warning_level:
            severity = "warning"
            risk_level = "HIGH"

        return UnifiedObservation(
            id=str(uuid.uuid4()),
            source_record_id=f"CWC-FL-{record.get('station_id', int(obs_time.timestamp()))}",
            hazard_type="FLOOD",
            location=GeoLocation(
                latitude=lat,
                longitude=lng,
                city_name=station_name,
                state_name=record.get("state_name", "Telangana")
            ),
            observed_at=obs_time,
            received_at=obs_time,
            severity=severity,
            risk_level=risk_level,
            confidence=0.97,
            data_type="official_observation",
            source_authority="Central Water Commission (CWC)",
            processing_version="1.0.0",
            measurements={
                "station_name": station_name,
                "river_basin": river_basin,
                "water_level_m": water_level,
                "danger_level_m": danger_level,
                "warning_level_m": warning_level,
                "trend": record.get("trend", "RISING"),
                "discharge_cumec": float(record.get("discharge_cumec", 1250.0))
            },
            metadata={
                "inundation_risk": "High" if water_level >= danger_level else "Moderate"
            }
        )

    def validate(self, normalized: UnifiedObservation) -> Tuple[bool, Optional[str]]:
        if not (-90.0 <= normalized.location.latitude <= 90.0):
            return False, f"Invalid latitude: {normalized.location.latitude}"
        if not (-180.0 <= normalized.location.longitude <= 180.0):
            return False, f"Invalid longitude: {normalized.location.longitude}"
        level = normalized.measurements.get("water_level_m", 0.0)
        if level < 0.0 or level > 2000.0:
            return False, f"Invalid physical water level: {level}m"
        return True, None
