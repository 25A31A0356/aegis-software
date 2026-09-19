"""
AEGIS UNIFIED DATA CORE - Physical Unit Normalization Engine
Converts all raw meteorological and hydro-seismological values to standard SI / Unified AEGIS units.
Standard AEGIS Units:
- Temperature: Celsius (°C)
- Speed / Wind: km/h
- Precipitation / Water: mm
- Pressure: hPa
- Distance / Elevation: meters (m) / kilometers (km)
- Seismic: Moment / Richter Magnitude (M)
"""
from typing import Optional, Tuple


class UnitConverter:
    @staticmethod
    def normalize_temperature(value: float, source_unit: str = "celsius") -> Tuple[float, str]:
        """Converts to Celsius (°C)"""
        unit = source_unit.lower().strip()
        if unit in ("c", "celsius", "degc", "°c"):
            return round(value, 2), "°C"
        elif unit in ("f", "fahrenheit", "degf", "°f"):
            c = (value - 32.0) * 5.0 / 9.0
            return round(c, 2), "°C"
        elif unit in ("k", "kelvin"):
            c = value - 273.15
            return round(c, 2), "°C"
        return round(value, 2), "°C"

    @staticmethod
    def normalize_speed(value: float, source_unit: str = "km/h") -> Tuple[float, str]:
        """Converts to km/h"""
        unit = source_unit.lower().strip()
        if unit in ("km/h", "kmh", "kph"):
            return round(value, 2), "km/h"
        elif unit in ("m/s", "mps"):
            kmh = value * 3.6
            return round(kmh, 2), "km/h"
        elif unit in ("knot", "knots", "kt"):
            kmh = value * 1.852
            return round(kmh, 2), "km/h"
        elif unit in ("mph", "miles/hour"):
            kmh = value * 1.60934
            return round(kmh, 2), "km/h"
        return round(value, 2), "km/h"

    @staticmethod
    def normalize_precipitation(value: float, source_unit: str = "mm") -> Tuple[float, str]:
        """Converts to mm"""
        unit = source_unit.lower().strip()
        if unit in ("mm", "millimeter", "millimeters"):
            return round(value, 2), "mm"
        elif unit in ("in", "inch", "inches"):
            mm = value * 25.4
            return round(mm, 2), "mm"
        elif unit in ("cm", "centimeter"):
            mm = value * 10.0
            return round(mm, 2), "mm"
        return round(value, 2), "mm"

    @staticmethod
    def normalize_pressure(value: float, source_unit: str = "hpa") -> Tuple[float, str]:
        """Converts to hPa (hectopascals / millibars)"""
        unit = source_unit.lower().strip()
        if unit in ("hpa", "mb", "mbar", "hectopascal"):
            return round(value, 2), "hPa"
        elif unit in ("pa", "pascal"):
            hpa = value / 100.0
            return round(hpa, 2), "hPa"
        elif unit in ("inhg", "in_hg"):
            hpa = value * 33.8639
            return round(hpa, 2), "hPa"
        elif unit in ("atm", "atmosphere"):
            hpa = value * 1013.25
            return round(hpa, 2), "hPa"
        return round(value, 2), "hPa"

    @staticmethod
    def normalize_distance(value: float, source_unit: str = "km") -> Tuple[float, str]:
        """Converts to km"""
        unit = source_unit.lower().strip()
        if unit in ("km", "kilometer", "kilometers"):
            return round(value, 2), "km"
        elif unit in ("m", "meter", "meters"):
            return round(value / 1000.0, 3), "km"
        elif unit in ("mi", "mile", "miles"):
            return round(value * 1.60934, 2), "km"
        elif unit in ("ft", "feet"):
            return round(value * 0.0003048, 3), "km"
        return round(value, 2), "km"
