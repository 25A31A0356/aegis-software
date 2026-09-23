"""
AEGIS UNIFIED DATA CORE - Unit Tests for Automatic Field Detection & Mapping
"""
from backend.app.ingestion.detector import FieldDetector
from backend.app.providers.adapters.custom_http import CustomHttpProvider


def test_field_detector_weather_payload():
    sample_payload = {
        "main": {
            "temp": 31.5,
            "humidity": 78,
            "pressure": 1008
        },
        "wind": {
            "speed": 18.5,
            "deg": 230
        },
        "coord": {
            "lat": 16.50,
            "lon": 80.64
        }
    }

    detected = FieldDetector.detect_fields(sample_payload)
    detected_fields = {d.detected_aegis_field: d for d in detected}

    assert "temperature" in detected_fields
    assert detected_fields["temperature"].external_path == "main.temp"
    assert detected_fields["temperature"].confidence in ("HIGH", "MEDIUM")

    assert "humidity" in detected_fields
    assert detected_fields["humidity"].external_path == "main.humidity"

    assert "wind_speed" in detected_fields
    assert detected_fields["wind_speed"].external_path == "wind.speed"

    assert "latitude" in detected_fields
    assert detected_fields["latitude"].external_path == "coord.lat"


def test_custom_http_provider_mapping():
    sample_record = {
        "main": {"temp": 86.0},  # Fahrenheit
        "wind": {"speed": 10.0},  # m/s
        "coord": {"lat": 19.07, "lon": 72.87}
    }

    mappings = [
        {"external_field_path": "main.temp", "aegis_field_name": "temperature", "source_unit": "fahrenheit", "transformation_rule": "fahrenheit_to_celsius"},
        {"external_field_path": "wind.speed", "aegis_field_name": "wind_speed", "source_unit": "m/s", "transformation_rule": "ms_to_kmh"},
        {"external_field_path": "coord.lat", "aegis_field_name": "latitude", "source_unit": "standard", "transformation_rule": "direct"},
        {"external_field_path": "coord.lon", "aegis_field_name": "longitude", "source_unit": "standard", "transformation_rule": "direct"},
    ]

    provider = CustomHttpProvider(
        name="Test Provider",
        base_url="https://api.example.com",
        field_mappings=mappings
    )

    norm = provider.normalize(sample_record)
    assert norm is not None
    assert norm.location.latitude == 19.07
    assert norm.location.longitude == 72.87
    # 86 F = 30.0 C
    assert abs(norm.measurements["temperature"] - 30.0) < 0.1
    # 10 m/s = 36 km/h
    assert abs(norm.measurements["wind_speed"] - 36.0) < 0.1
