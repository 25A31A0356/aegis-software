"""
AEGIS UNIFIED DATA CORE - Standardized Unified Data Models
Defines the single unified schema outputted across all hazard types,
guaranteeing consistent fields for Web and Mobile clients.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class GeoLocation(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    city_name: Optional[str] = None
    district_name: Optional[str] = None
    state_name: Optional[str] = None


class UnifiedObservation(BaseModel):
    id: str
    data_source_id: Optional[str] = None
    source_record_id: Optional[str] = None
    hazard_type: str = Field(..., examples=["WEATHER"])  # WEATHER, EARTHQUAKE, FLOOD, CYCLONE, STORM, LIGHTNING, WILDFIRE, AIR_QUALITY, OTHER
    location: GeoLocation
    observed_at: datetime
    received_at: datetime
    valid_until: Optional[datetime] = None
    severity: str = Field(default="moderate", examples=["moderate"])  # minor, moderate, warning, critical
    risk_level: str = Field(default="MODERATE", examples=["MODERATE"])  # LOW, MODERATE, HIGH, VERY_HIGH, EXTREME
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    data_type: str = Field(default="official_observation")  # official_observation, derived, forecast, ai_analysis, cached
    source_authority: str = Field(default="External Provider")
    processing_version: str = Field(default="1.0.0")
    measurements: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WeatherTelemetryPayload(BaseModel):
    city_name: str
    state_name: str
    coordinates: List[float] = Field(..., min_length=2, max_length=2)
    observed_at: str
    condition: str
    condition_code: str = "sunny"
    temperature: float
    feels_like: float
    humidity: float
    wind_speed: float
    wind_direction: str
    rain_probability: float
    rainfall_expected_mm: float
    uv_index: float
    barometric_pressure_hpa: float
    visibility_km: float
    air_quality_index: float
    air_quality_status: str
    source: str = "AEGIS Data Core"
    provenance_type: str = "official_observation"
    freshness_status: str = "fresh"


class AlertItemSchema(BaseModel):
    id: str
    alert_code: str
    title: str
    hazard_type: str
    severity: str  # critical, warning, moderate, minor
    status: str  # active, monitoring, resolved, expired
    headline: str
    description: str
    instruction: Optional[str] = None
    location: Dict[str, Any]
    source: Dict[str, Any]
    published_at: str
    valid_until: Optional[str] = None
    provenance_type: str = "official_warning"


class EarthquakeEventSchema(BaseModel):
    id: str
    magnitude: float
    depth_km: float
    place: str
    latitude: float
    longitude: float
    time: str
    source_authority: str = "USGS/National Seismology"
    severity: str = "moderate"
    status: str = "monitoring"


class FloodTelemetrySchema(BaseModel):
    station_id: str
    station_name: str
    river_basin: str
    state_name: str
    water_level_m: float
    danger_level_m: float
    warning_level_m: float
    trend: str  # RISING, FALLING, STEADY
    latitude: float
    longitude: float
    observed_at: str
    source_agency: str = "Central Water Commission (CWC)"


class CycloneTrackSchema(BaseModel):
    system_id: str
    name: str
    intensity_grade: str  # Depression, Deep Depression, Cyclonic Storm, Severe Cyclonic Storm, Super Cyclone
    max_sustained_wind_kmh: float
    central_pressure_hpa: float
    current_lat: float
    current_lng: float
    forecast_track: List[Dict[str, Any]]
    bulletin_time: str
    source_agency: str = "IMD Cyclone Warning Division"


class AirQualitySchema(BaseModel):
    station_name: str
    state_name: str
    aqi: int
    aqi_status: str  # Good, Moderate, Unhealthy, Severe, Hazardous
    prominent_pollutant: str
    pm2_5: float
    pm10: float
    no2: float
    so2: float
    co: float
    ozone: float
    latitude: float
    longitude: float
    observed_at: str
    source_agency: str = "CPCB / Open-Meteo Air Quality"


class RiskEvaluationResponse(BaseModel):
    location: GeoLocation
    composite_risk_score: float  # 0 to 100
    risk_level: str  # LOW, MODERATE, HIGH, VERY_HIGH, EXTREME
    primary_hazard: str
    contributing_factors: List[Dict[str, Any]]
    is_aegis_derived: bool = True
    provenance: str = "AEGIS Multi-Source Correlation Engine"
    evaluated_at: str
