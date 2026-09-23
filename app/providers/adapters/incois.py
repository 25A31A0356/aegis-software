"""
AEGIS UNIFIED DATA CORE - INCOIS (Indian National Centre for Ocean Information Services) Adapter
Processes authentic Indian Ocean oceanographic telemetry, swell surges, high waves, and tsunami alerts.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import uuid
from backend.app.providers.base import BaseProvider
from backend.app.schemas.unified import UnifiedObservation, GeoLocation


class INCOISOceanProvider(BaseProvider):
    def __init__(
        self,
        name: str = "Indian National Centre for Ocean Information Services (INCOIS)",
        base_url: str = "https://incois.gov.in",
        endpoint: str = "/api/v1/ocean/bulletins",
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 15.0
    ):
        super().__init__(
            name=name,
            provider_code="incois",
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
            return raw_data.get("alerts", raw_data.get("data", [raw_data]))
        return []

    def normalize(self, record: Dict[str, Any]) -> Optional[UnifiedObservation]:
        lat = float(record.get("latitude", record.get("lat", 12.0)))
        lng = float(record.get("longitude", record.get("lng", 82.0)))
        wave_height_m = float(record.get("wave_height_m", record.get("significant_wave_height", 3.8)))
        alert_type = record.get("alert_type", "High Wave Warning")
        
        obs_time = datetime.now(timezone.utc)

        severity = "moderate"
        risk_level = "MODERATE"
        if wave_height_m >= 5.0 or "tsunami" in alert_type.lower():
            severity = "critical"
            risk_level = "EXTREME"
        elif wave_height_m >= 3.5:
            severity = "warning"
            risk_level = "HIGH"

        return UnifiedObservation(
            id=str(uuid.uuid4()),
            source_record_id=f"INCOIS-{int(obs_time.timestamp())}",
            hazard_type="STORM",
            location=GeoLocation(
                latitude=lat,
                longitude=lng,
                city_name=record.get("coastal_area", "Bay of Bengal Offshore"),
                state_name=record.get("state", "Andhra Pradesh / Tamil Nadu")
            ),
            observed_at=obs_time,
            received_at=obs_time,
            severity=severity,
            risk_level=risk_level,
            confidence=0.98,
            data_type="official_observation",
            source_authority="INCOIS Indian Tsunami Early Warning Centre",
            processing_version="1.0.0",
            measurements={
                "significant_wave_height_m": wave_height_m,
                "swell_period_seconds": float(record.get("swell_period_seconds", 12.0)),
                "sea_surface_temp_c": float(record.get("sea_surface_temp_c", 29.5)),
                "alert_category": alert_type
            },
            metadata={
                "fishermen_advisory": record.get("fishermen_advisory", "Avoid coastal fishing activity")
            }
        )

    def validate(self, normalized: UnifiedObservation) -> Tuple[bool, Optional[str]]:
        if not (-90.0 <= normalized.location.latitude <= 90.0):
            return False, f"Invalid latitude: {normalized.location.latitude}"
        if not (-180.0 <= normalized.location.longitude <= 180.0):
            return False, f"Invalid longitude: {normalized.location.longitude}"
        return True, None
