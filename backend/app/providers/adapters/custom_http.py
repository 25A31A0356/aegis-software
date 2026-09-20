"""
AEGIS UNIFIED DATA CORE - Universal Custom HTTP Provider Adapter
Dynamic adapter that uses administrator-configured field mappings, unit conversions,
and custom parameters to ingest data from any standard external REST/HTTP API.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import uuid
from backend.app.providers.base import BaseProvider
from backend.app.schemas.unified import UnifiedObservation, GeoLocation
from backend.app.utils.units import UnitConverter


class CustomHttpProvider(BaseProvider):
    def __init__(
        self,
        name: str,
        base_url: str,
        endpoint: str = "",
        category: str = "WEATHER",
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        field_mappings: Optional[List[Dict[str, Any]]] = None,
        timeout_seconds: float = 15.0
    ):
        super().__init__(
            name=name,
            provider_code="custom_http",
            base_url=base_url,
            endpoint=endpoint,
            api_key=api_key,
            headers=headers,
            params=params,
            timeout_seconds=timeout_seconds
        )
        self.category = category.upper()
        self.field_mappings = field_mappings or []

    def _extract_path_value(self, obj: Any, path: str) -> Any:
        """Navigates nested dot-notation paths (e.g. 'main.temp', 'coord.lat')."""
        if not path or not isinstance(obj, dict):
            return None
        parts = path.split(".")
        curr = obj
        for part in parts:
            if isinstance(curr, dict) and part in curr:
                curr = curr[part]
            elif isinstance(curr, list) and part.isdigit() and int(part) < len(curr):
                curr = curr[int(part)]
            else:
                return None
        return curr

    def parse(self, raw_data: Any) -> List[Dict[str, Any]]:
        if isinstance(raw_data, list):
            return raw_data
        elif isinstance(raw_data, dict):
            # If root contains a list under 'items', 'data', 'features', or 'results'
            for key in ("items", "data", "features", "results", "records", "list"):
                if key in raw_data and isinstance(raw_data[key], list):
                    return raw_data[key]
            return [raw_data]
        return []

    def normalize(self, record: Dict[str, Any]) -> Optional[UnifiedObservation]:
        measurements: Dict[str, Any] = {}
        lat = 19.0760
        lng = 72.8777
        city_name = "Monitored Station"

        for mapping in self.field_mappings:
            ext_path = mapping.get("external_field_path")
            aegis_field = mapping.get("aegis_field_name")
            source_unit = mapping.get("source_unit", "standard")
            rule = mapping.get("transformation_rule", "direct")

            if not aegis_field or not ext_path:
                continue

            aegis_field_str = str(aegis_field)
            aegis_field_lower = aegis_field_str.lower()

            val = self._extract_path_value(record, ext_path)
            if val is None:
                continue

            try:
                num_val = float(val)
                # Apply unit conversions
                if "temp" in aegis_field_lower:
                    norm_val, _ = UnitConverter.normalize_temperature(num_val, source_unit)
                    measurements[aegis_field_str] = norm_val
                elif "wind" in aegis_field_lower or "speed" in aegis_field_lower:
                    norm_val, _ = UnitConverter.normalize_speed(num_val, source_unit)
                    measurements[aegis_field_str] = norm_val
                elif "pressure" in aegis_field_lower:
                    norm_val, _ = UnitConverter.normalize_pressure(num_val, source_unit)
                    measurements[aegis_field_str] = norm_val
                elif "precip" in aegis_field_lower or "rain" in aegis_field_lower or "water" in aegis_field_lower:
                    norm_val, _ = UnitConverter.normalize_precipitation(num_val, source_unit)
                    measurements[aegis_field_str] = norm_val
                elif aegis_field_lower in ("latitude", "lat"):
                    lat = num_val
                elif aegis_field_lower in ("longitude", "lng", "lon"):
                    lng = num_val
                else:
                    measurements[aegis_field_str] = num_val
            except (ValueError, TypeError):
                if aegis_field_lower in ("city", "city_name", "location"):
                    city_name = str(val)
                else:
                    measurements[aegis_field_str] = val

        obs_time = datetime.now(timezone.utc)

        return UnifiedObservation(
            id=str(uuid.uuid4()),
            source_record_id=f"CUSTOM-{int(obs_time.timestamp())}",
            hazard_type=self.category,
            location=GeoLocation(
                latitude=lat,
                longitude=lng,
                city_name=city_name
            ),
            observed_at=obs_time,
            received_at=obs_time,
            severity="moderate",
            risk_level="MODERATE",
            confidence=0.90,
            data_type="official_observation",
            source_authority=self.name,
            processing_version="1.0.0",
            measurements=measurements,
            metadata={"source_name": self.name}
        )

    def validate(self, normalized: UnifiedObservation) -> Tuple[bool, Optional[str]]:
        if not (-90.0 <= normalized.location.latitude <= 90.0):
            return False, f"Invalid latitude: {normalized.location.latitude}"
        if not (-180.0 <= normalized.location.longitude <= 180.0):
            return False, f"Invalid longitude: {normalized.location.longitude}"
        return True, None
