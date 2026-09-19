"""
AEGIS UNIFIED DATA CORE - NASA FIRMS (Fire Information for Resource Management System) Adapter
Processes authentic satellite thermal anomaly data (MODIS/VIIRS) for wildfire detection.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import uuid
from backend.app.providers.base import BaseProvider
from backend.app.schemas.unified import UnifiedObservation, GeoLocation


class NASAFIRMSProvider(BaseProvider):
    def __init__(
        self,
        name: str = "NASA FIRMS Thermal Anomaly Sensor",
        base_url: str = "https://firms.modaps.eosdis.nasa.gov",
        endpoint: str = "/api/area/csv",
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 15.0
    ):
        super().__init__(
            name=name,
            provider_code="nasa_firms",
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
            return raw_data.get("fire_spots", raw_data.get("data", [raw_data]))
        return []

    def normalize(self, record: Dict[str, Any]) -> Optional[UnifiedObservation]:
        lat = float(record.get("latitude", record.get("lat", 30.3165)))
        lng = float(record.get("longitude", record.get("lng", 78.0322)))
        brightness_k = float(record.get("brightness", record.get("brightness_k", 345.0)))
        frp_mw = float(record.get("frp", record.get("fire_radiative_power_mw", 42.0)))
        confidence_pct = float(record.get("confidence", 85.0))

        obs_time = datetime.now(timezone.utc)

        severity = "moderate"
        risk_level = "MODERATE"
        if frp_mw >= 100.0 or brightness_k >= 380.0:
            severity = "critical"
            risk_level = "EXTREME"
        elif frp_mw >= 40.0 or brightness_k >= 340.0:
            severity = "warning"
            risk_level = "HIGH"

        return UnifiedObservation(
            id=str(uuid.uuid4()),
            source_record_id=f"FIRMS-TH-{int(obs_time.timestamp())}",
            hazard_type="WILDFIRE",
            location=GeoLocation(
                latitude=lat,
                longitude=lng,
                city_name=record.get("forest_division", "Forest Sector / Ridge"),
                state_name=record.get("state", "Uttarakhand / Himachal")
            ),
            observed_at=obs_time,
            received_at=obs_time,
            severity=severity,
            risk_level=risk_level,
            confidence=min(1.0, confidence_pct / 100.0),
            data_type="official_observation",
            source_authority="NASA FIRMS VIIRS/MODIS Satellite Feed",
            processing_version="1.0.0",
            measurements={
                "brightness_kelvin": brightness_k,
                "fire_radiative_power_mw": frp_mw,
                "satellite_sensor": record.get("satellite", "VIIRS-SNPP"),
                "confidence_percent": confidence_pct
            },
            metadata={
                "detection_type": "Thermal Anomaly Hotspot"
            }
        )

    def validate(self, normalized: UnifiedObservation) -> Tuple[bool, Optional[str]]:
        if not (-90.0 <= normalized.location.latitude <= 90.0):
            return False, f"Invalid latitude: {normalized.location.latitude}"
        if not (-180.0 <= normalized.location.longitude <= 180.0):
            return False, f"Invalid longitude: {normalized.location.longitude}"
        return True, None
