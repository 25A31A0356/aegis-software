"""
AEGIS UNIFIED DATA CORE - Telemetry & Schema Validator
Strict validation ensuring that malformed, out-of-bounds, or physically impossible data is flagged or rejected.
"""
from typing import Tuple, Optional, Dict, Any
from datetime import datetime
from backend.app.schemas.unified import UnifiedObservation


class TelemetryValidator:
    @staticmethod
    def validate_observation(obs: UnifiedObservation) -> Tuple[bool, Optional[str]]:
        # 1. Geographic Coordinate Bounds
        lat = obs.location.latitude
        lng = obs.location.longitude
        if not (-90.0 <= lat <= 90.0):
            return False, f"Latitude {lat} is out of physical range [-90, +90]."
        if not (-180.0 <= lng <= 180.0):
            return False, f"Longitude {lng} is out of physical range [-180, +180]."

        # 2. Timestamp sanity (cannot be > 2 days in future or > 30 days in past for real-time telemetry)
        now = datetime.now(obs.observed_at.tzinfo)
        diff_hours = (obs.observed_at - now).total_seconds() / 3600.0
        if diff_hours > 48.0:
            return False, f"Observation timestamp is too far in future (+{diff_hours:.1f} hours)."
        if diff_hours < -720.0:  # > 30 days
            return False, f"Observation timestamp is too old ({diff_hours:.1f} hours ago)."

        # 3. Domain Metric Physical Sanity Checks
        m = obs.measurements
        if "temperature_c" in m:
            t = m["temperature_c"]
            if not (-80.0 <= t <= 65.0):
                return False, f"Physically impossible temperature reading: {t}°C"

        if "wind_speed_kmh" in m:
            ws = m["wind_speed_kmh"]
            if not (0.0 <= ws <= 450.0):
                return False, f"Physically impossible wind speed reading: {ws} km/h"

        if "pressure_hpa" in m:
            p = m["pressure_hpa"]
            if not (850.0 <= p <= 1100.0):
                return False, f"Physically impossible atmospheric pressure: {p} hPa"

        if "magnitude" in m:
            mag = m["magnitude"]
            if not (0.0 <= mag <= 10.0):
                return False, f"Seismic magnitude out of range [0, 10]: {mag}"

        return True, None
