"""
AEGIS UNIFIED DATA CORE - Telemetry Validator Tests
"""
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from backend.app.schemas.unified import UnifiedObservation, GeoLocation
from backend.app.ingestion.validator import TelemetryValidator


def test_valid_observation():
    obs = UnifiedObservation(
        id="test-obs-1",
        hazard_type="WEATHER",
        location=GeoLocation(latitude=19.07, longitude=72.87),
        observed_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        measurements={"temperature_c": 32.0, "wind_speed_kmh": 22.0, "pressure_hpa": 1010.0}
    )
    is_valid, err = TelemetryValidator.validate_observation(obs)
    assert is_valid is True
    assert err is None


def test_invalid_latitude_pydantic():
    with pytest.raises(ValidationError):
        GeoLocation(latitude=105.0, longitude=72.87)


def test_impossible_temperature():
    obs = UnifiedObservation(
        id="test-obs-3",
        hazard_type="WEATHER",
        location=GeoLocation(latitude=19.07, longitude=72.87),
        observed_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        measurements={"temperature_c": 150.0}  # Impossible 150°C
    )
    is_valid, err = TelemetryValidator.validate_observation(obs)
    assert is_valid is False
    assert "Physically impossible temperature reading" in err
