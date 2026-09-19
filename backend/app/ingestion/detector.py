"""
AEGIS UNIFIED DATA CORE - Automatic Field Detection Engine
Inspects arbitrary JSON/GeoJSON payload structures and heuristically discovers
likely meteorological, seismic, hydro, and geographic fields with confidence ratings.
"""
from typing import Dict, Any, List
from backend.app.schemas.source import DetectedField


# Known semantic field alias dictionaries
FIELD_PATTERNS = {
    "temperature": (["temp", "temperature", "temp_c", "temp_f", "temperature_2m", "apparent_temp", "feels_like", "t2m"], "°C", "kelvin_to_celsius_if_gt_150"),
    "humidity": (["humidity", "rh", "relative_humidity", "humidity_2m", "hum", "rel_hum"], "%", "direct"),
    "wind_speed": (["wind", "wind_speed", "wind_speed_10m", "ws", "speed", "wind_spd", "gust"], "km/h", "ms_to_kmh_if_mps"),
    "wind_direction": (["wind_dir", "wind_direction", "wind_direction_10m", "wd", "wind_deg"], "deg", "direct"),
    "precipitation": (["precip", "precipitation", "rain", "rainfall", "rain_mm", "precipitation_probability"], "mm", "direct"),
    "pressure": (["pressure", "surface_pressure", "barometric_pressure", "pres", "p_hpa", "slp"], "hPa", "direct"),
    "latitude": (["lat", "latitude", "coord_lat", "y"], "deg", "direct"),
    "longitude": (["lon", "lng", "long", "longitude", "coord_lon", "x"], "deg", "direct"),
    "magnitude": (["mag", "magnitude", "richter", "richter_scale", "eq_mag"], "M", "direct"),
    "depth": (["depth", "depth_km", "hypocenter_depth", "focal_depth"], "km", "direct"),
    "water_level": (["water_level", "gauge_level", "river_level", "flood_level", "level_m", "stage"], "m", "direct"),
    "air_quality_index": (["aqi", "us_aqi", "air_quality", "in_aqi", "pm25_aqi"], "AQI", "direct"),
    "pm2_5": (["pm2_5", "pm25", "particulate_2_5"], "µg/m³", "direct"),
    "pm10": (["pm10", "particulate_10"], "µg/m³", "direct"),
}


class FieldDetector:
    @classmethod
    def detect_fields(cls, sample_data: Any, max_depth: int = 4) -> List[DetectedField]:
        """Traverses payload and extracts detected field paths."""
        detected: List[DetectedField] = []
        cls._traverse(sample_data, "", detected, current_depth=0, max_depth=max_depth)
        return detected

    @classmethod
    def _traverse(cls, obj: Any, current_path: str, detected: List[DetectedField], current_depth: int, max_depth: int):
        if current_depth > max_depth:
            return

        if isinstance(obj, dict):
            for key, val in obj.items():
                new_path = f"{current_path}.{key}" if current_path else key
                if isinstance(val, (dict, list)):
                    cls._traverse(val, new_path, detected, current_depth + 1, max_depth)
                else:
                    match = cls._match_key(key, val)
                    if match:
                        aegis_field, confidence, unit, rule = match
                        detected.append(DetectedField(
                            external_path=new_path,
                            sample_value=val,
                            detected_aegis_field=aegis_field,
                            confidence=confidence,
                            suggested_unit=unit,
                            suggested_rule=rule
                        ))
        elif isinstance(obj, list) and obj:
            # Inspect first element if array of objects
            cls._traverse(obj[0], current_path, detected, current_depth + 1, max_depth)

    @classmethod
    def _match_key(cls, key: str, val: Any) -> Any:
        lower_key = key.lower().replace("-", "_").strip()
        for field_name, (aliases, unit, rule) in FIELD_PATTERNS.items():
            if lower_key in aliases:
                return field_name, "HIGH", unit, rule
            for alias in aliases:
                if alias in lower_key:
                    return field_name, "MEDIUM", unit, rule
        return None
