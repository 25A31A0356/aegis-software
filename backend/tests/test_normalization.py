"""
AEGIS UNIFIED DATA CORE - Unit Conversion Tests
"""
from backend.app.utils.units import UnitConverter


def test_temperature_normalization():
    # 212°F -> 100°C
    val, unit = UnitConverter.normalize_temperature(212.0, "fahrenheit")
    assert abs(val - 100.0) < 0.01
    assert unit == "°C"

    # 300 K -> 26.85°C
    val, unit = UnitConverter.normalize_temperature(300.0, "kelvin")
    assert abs(val - 26.85) < 0.01
    assert unit == "°C"

    # 25°C -> 25°C
    val, unit = UnitConverter.normalize_temperature(25.0, "celsius")
    assert val == 25.0


def test_speed_normalization():
    # 10 m/s -> 36 km/h
    val, unit = UnitConverter.normalize_speed(10.0, "m/s")
    assert abs(val - 36.0) < 0.01
    assert unit == "km/h"

    # 50 knots -> 92.6 km/h
    val, unit = UnitConverter.normalize_speed(50.0, "knots")
    assert abs(val - 92.6) < 0.1
    assert unit == "km/h"


def test_precipitation_normalization():
    # 2 inches -> 50.8 mm
    val, unit = UnitConverter.normalize_precipitation(2.0, "inches")
    assert abs(val - 50.8) < 0.01
    assert unit == "mm"


def test_pressure_normalization():
    # 101325 Pa -> 1013.25 hPa
    val, unit = UnitConverter.normalize_pressure(101325.0, "pascal")
    assert abs(val - 1013.25) < 0.01
    assert unit == "hPa"
