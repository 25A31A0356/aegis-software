"""
AEGIS UNIFIED DATA CORE - IMD (India Meteorological Department) Adapter
Processes IMD cyclone bulletins, depression tracks, and heavy rainfall warnings.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import uuid
from backend.app.providers.base import BaseProvider
from backend.app.schemas.unified import UnifiedObservation, GeoLocation


class IMDProvider(BaseProvider):
    def __init__(
        self,
        name: str = "India Meteorological Department (IMD)",
        base_url: str = "https://mausam.imd.gov.in",
        endpoint: str = "/api/v1/telemetry",
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 15.0
    ):
        super().__init__(
            name=name,
            provider_code="imd",
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
            return raw_data.get("bulletins", raw_data.get("data", [raw_data]))
        return []

    def normalize(self, record: Dict[str, Any]) -> Optional[UnifiedObservation]:
        lat = float(record.get("latitude", record.get("lat", 19.81)))
        lng = float(record.get("longitude", record.get("lon", 85.83)))
        system_name = record.get("system_name", record.get("title", "IMD Tropical Disturbance"))
        wind_speed_kmh = float(record.get("max_sustained_wind_kmh", record.get("wind_speed", 75.0)))
        pressure_hpa = float(record.get("central_pressure_hpa", 992.0))
        
        obs_time = datetime.now(timezone.utc)

        severity = "warning"
        risk_level = "HIGH"
        if wind_speed_kmh >= 90 or pressure_hpa <= 980:
            severity = "critical"
            risk_level = "EXTREME"

        return UnifiedObservation(
            id=str(uuid.uuid4()),
            source_record_id=f"IMD-CYC-{record.get('bulletin_id', int(obs_time.timestamp()))}",
            hazard_type="CYCLONE",
            location=GeoLocation(
                latitude=lat,
                longitude=lng,
                city_name=record.get("coastal_district", "Coastal Sector"),
                state_name=record.get("state_name", "Odisha")
            ),
            observed_at=obs_time,
            received_at=obs_time,
            severity=severity,
            risk_level=risk_level,
            confidence=0.96,
            data_type="official_observation",
            source_authority="India Meteorological Department (IMD)",
            processing_version="1.0.0",
            measurements={
                "system_name": system_name,
                "max_sustained_wind_kmh": wind_speed_kmh,
                "central_pressure_hpa": pressure_hpa,
                "movement_speed_kmh": float(record.get("movement_speed_kmh", 18.0)),
                "movement_direction": record.get("movement_direction", "NNW")
            },
            metadata={
                "landfall_prediction": record.get("landfall_prediction", "Coastal Inundation Watch"),
                "bulletin_number": record.get("bulletin_id", "IMD-RSMC-2026")
            }
        )

    def validate(self, normalized: UnifiedObservation) -> Tuple[bool, Optional[str]]:
        if not (-90.0 <= normalized.location.latitude <= 90.0):
            return False, f"Invalid latitude: {normalized.location.latitude}"
        if not (-180.0 <= normalized.location.longitude <= 180.0):
            return False, f"Invalid longitude: {normalized.location.longitude}"
        return True, None
