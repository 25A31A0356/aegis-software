"""
AEGIS UNIFIED DATA CORE - Open-Meteo Weather & Telemetry Adapter
Official non-commercial meteorological telemetry stream adapter for India and global regions.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import uuid
from backend.app.providers.base import BaseProvider
from backend.app.schemas.unified import UnifiedObservation, GeoLocation
from backend.app.utils.units import UnitConverter


class OpenMeteoProvider(BaseProvider):
    def __init__(
        self,
        name: str = "Open-Meteo Meteorological Service",
        base_url: str = "https://api.open-meteo.com/v1",
        endpoint: str = "/forecast",
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 15.0
    ):
        default_params = {
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m,uv_index,cloud_cover,weather_code",
            "timezone": "Asia/Kolkata"
        }
        merged_params = {**default_params, **(params or {})}
        super().__init__(
            name=name,
            provider_code="open_meteo",
            base_url=base_url,
            endpoint=endpoint,
            api_key=api_key,
            headers=headers,
            params=merged_params,
            timeout_seconds=timeout_seconds
        )

    def parse(self, raw_data: Any) -> List[Dict[str, Any]]:
        if not isinstance(raw_data, dict):
            return []
        current = raw_data.get("current", {})
        if not current:
            return []
        record = {
            "latitude": raw_data.get("latitude"),
            "longitude": raw_data.get("longitude"),
            "elevation": raw_data.get("elevation"),
            "time": current.get("time"),
            "temperature_c": current.get("temperature_2m"),
            "humidity_pct": current.get("relative_humidity_2m"),
            "apparent_temp_c": current.get("apparent_temperature"),
            "precip_mm": current.get("precipitation"),
            "pressure_hpa": current.get("surface_pressure"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "wind_direction_deg": current.get("wind_direction_10m"),
            "wind_gusts_kmh": current.get("wind_gusts_10m"),
            "uv_index": current.get("uv_index"),
            "cloud_cover_pct": current.get("cloud_cover"),
            "weather_code": current.get("weather_code", 0),
        }
        return [record]

    def normalize(self, record: Dict[str, Any]) -> Optional[UnifiedObservation]:
        lat = float(record.get("latitude", 0.0))
        lng = float(record.get("longitude", 0.0))
        obs_time_str = record.get("time")
        
        try:
            obs_time = datetime.fromisoformat(obs_time_str.replace("Z", "+00:00")) if obs_time_str else datetime.now(timezone.utc)
        except Exception:
            obs_time = datetime.now(timezone.utc)

        temp_c, _ = UnitConverter.normalize_temperature(float(record.get("temperature_c", 0.0)), "celsius")
        wind_kmh, _ = UnitConverter.normalize_speed(float(record.get("wind_speed_kmh", 0.0)), "km/h")
        precip_mm, _ = UnitConverter.normalize_precipitation(float(record.get("precip_mm", 0.0)), "mm")
        pressure_hpa, _ = UnitConverter.normalize_pressure(float(record.get("pressure_hpa", 1013.25)), "hpa")

        # Determine severity and risk level
        severity = "moderate"
        risk_level = "MODERATE"
        if wind_kmh >= 65 or precip_mm >= 30:
            severity = "critical"
            risk_level = "EXTREME"
        elif wind_kmh >= 45 or precip_mm >= 15:
            severity = "warning"
            risk_level = "HIGH"
        elif temp_c >= 42 or temp_c <= 3:
            severity = "warning"
            risk_level = "HIGH"

        return UnifiedObservation(
            id=str(uuid.uuid4()),
            source_record_id=f"OM-{lat:.2f}-{lng:.2f}-{int(obs_time.timestamp())}",
            hazard_type="WEATHER",
            location=GeoLocation(latitude=lat, longitude=lng),
            observed_at=obs_time,
            received_at=datetime.now(timezone.utc),
            severity=severity,
            risk_level=risk_level,
            confidence=0.95,
            data_type="official_observation",
            source_authority="Open-Meteo Meteorological Telemetry",
            processing_version="1.0.0",
            measurements={
                "temperature_c": temp_c,
                "apparent_temperature_c": record.get("apparent_temp_c", temp_c),
                "humidity_percent": record.get("humidity_pct", 50.0),
                "wind_speed_kmh": wind_kmh,
                "wind_direction_deg": record.get("wind_direction_deg", 0),
                "precipitation_mm": precip_mm,
                "pressure_hpa": pressure_hpa,
                "uv_index": record.get("uv_index", 0),
                "weather_code": record.get("weather_code", 0)
            },
            metadata={"elevation_m": record.get("elevation", 0)}
        )

    def validate(self, normalized: UnifiedObservation) -> Tuple[bool, Optional[str]]:
        if not (-90.0 <= normalized.location.latitude <= 90.0):
            return False, f"Invalid latitude: {normalized.location.latitude}"
        if not (-180.0 <= normalized.location.longitude <= 180.0):
            return False, f"Invalid longitude: {normalized.location.longitude}"
        temp = normalized.measurements.get("temperature_c")
        if temp is not None and not (-70.0 <= temp <= 65.0):
            return False, f"Unrealistic physical temperature value: {temp}°C"
        return True, None
