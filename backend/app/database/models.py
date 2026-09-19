"""
AEGIS UNIFIED DATA CORE - Database Schema & Data Models
Production PostgreSQL / PostGIS Schema with Time-Series & Observability structures.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey, Index, Enum
)
from sqlalchemy.orm import relationship
from backend.app.database.base import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "aegis_users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="public", nullable=False)  # admin, official, sdrf_officer, public
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class DataSource(Base):
    __tablename__ = "aegis_data_sources"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    provider_code = Column(String(50), nullable=False, index=True)  # imd, cwc, incois, usgs, nasa_firms, open_meteo, cpcb, custom_http
    category = Column(String(50), nullable=False, index=True)  # WEATHER, EARTHQUAKE, FLOOD, CYCLONE, STORM, LIGHTNING, WILDFIRE, AIR_QUALITY, DISASTER_ALERT, OTHER
    base_url = Column(String(1024), nullable=False)
    endpoint = Column(String(1024), default="", nullable=False)
    http_method = Column(String(10), default="GET", nullable=False)
    
    # Auth configuration (Secrets encrypted at rest via SecretVault)
    auth_type = Column(String(50), default="NONE", nullable=False)  # NONE, API_KEY_QUERY, API_KEY_HEADER, BEARER_TOKEN, BASIC_AUTH
    encrypted_api_key = Column(Text, default="", nullable=True)
    auth_header_name = Column(String(100), default="Authorization", nullable=True)
    auth_query_param = Column(String(100), default="api_key", nullable=True)
    
    # Ingestion Parameters
    request_params = Column(JSON, default=dict, nullable=False)
    request_headers = Column(JSON, default=dict, nullable=False)
    response_format = Column(String(20), default="JSON", nullable=False)  # JSON, XML, CSV, GEOJSON
    
    # Scheduling & Execution
    update_frequency_minutes = Column(Integer, default=5, nullable=False)
    cache_duration_seconds = Column(Integer, default=300, nullable=False)
    timeout_seconds = Column(Float, default=15.0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    
    # Source Health Tracking
    health_status = Column(String(50), default="INACTIVE", nullable=False)  # ACTIVE, HEALTHY, DEGRADED, FAILED, INACTIVE
    consecutive_failures = Column(Integer, default=0, nullable=False)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    last_response_time_ms = Column(Float, default=0.0, nullable=False)
    last_http_status = Column(Integer, nullable=True)
    last_error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    field_mappings = relationship("FieldMapping", back_populates="data_source", cascade="all, delete-orphan")
    raw_observations = relationship("RawObservation", back_populates="data_source", cascade="all, delete-orphan")
    normalized_observations = relationship("NormalizedObservation", back_populates="data_source", cascade="all, delete-orphan")


class FieldMapping(Base):
    __tablename__ = "aegis_field_mappings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    data_source_id = Column(String(36), ForeignKey("aegis_data_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    external_field_path = Column(String(255), nullable=False)  # e.g. 'main.temp', 'properties.mag'
    aegis_field_name = Column(String(100), nullable=False)     # e.g. 'temperature', 'magnitude'
    source_unit = Column(String(50), default="standard", nullable=True)
    target_unit = Column(String(50), default="standard", nullable=True)
    transformation_rule = Column(String(100), default="direct", nullable=False)  # direct, kelvin_to_celsius, ms_to_kmh, wmo_code
    confidence = Column(String(20), default="HIGH", nullable=False)  # HIGH, MEDIUM, LOW
    is_active = Column(Boolean, default=True, nullable=False)

    data_source = relationship("DataSource", back_populates="field_mappings")


class RawObservation(Base):
    __tablename__ = "aegis_raw_observations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    data_source_id = Column(String(36), ForeignKey("aegis_data_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    source_record_id = Column(String(255), nullable=True, index=True)
    payload_format = Column(String(20), default="JSON", nullable=False)
    raw_payload = Column(JSON, nullable=False)
    received_at = Column(DateTime(timezone=True), default=utc_now, index=True)

    data_source = relationship("DataSource", back_populates="raw_observations")


class NormalizedObservation(Base):
    __tablename__ = "aegis_normalized_observations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    data_source_id = Column(String(36), ForeignKey("aegis_data_sources.id", ondelete="SET NULL"), nullable=True, index=True)
    source_record_id = Column(String(255), nullable=True, index=True)
    hazard_type = Column(String(50), nullable=False, index=True)  # WEATHER, EARTHQUAKE, FLOOD, CYCLONE, STORM, LIGHTNING, WILDFIRE, AIR_QUALITY
    
    # Geospatial coordinates
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    location_name = Column(String(255), default="", nullable=True)
    state_name = Column(String(100), default="", nullable=True, index=True)
    district_name = Column(String(100), default="", nullable=True)
    
    # Timestamps & Freshness
    observed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    received_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    
    # Assessment & Provenance
    severity = Column(String(50), default="moderate", nullable=False)  # minor, moderate, warning, critical
    risk_level = Column(String(50), default="MODERATE", nullable=False)  # LOW, MODERATE, HIGH, VERY_HIGH, EXTREME
    confidence = Column(Float, default=1.0, nullable=False)
    data_type = Column(String(50), default="official_observation", nullable=False)  # official_observation, derived, forecast, ai_analysis, cached
    source_authority = Column(String(100), default="External Provider", nullable=False)
    processing_version = Column(String(20), default="1.0.0", nullable=False)
    
    # Dynamic normalized telemetry measurements
    # e.g. { "temperature": 31.5, "humidity": 78, "wind_speed": 22.4, "water_level_m": 4.2, "magnitude": 4.8 }
    measurements = Column(JSON, default=dict, nullable=False)
    metadata_json = Column(JSON, default=dict, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=utc_now)

    data_source = relationship("DataSource", back_populates="normalized_observations")

    # Composite indexing for high-speed spatial-temporal filtering
    __table_args__ = (
        Index("ix_obs_hazard_time", "hazard_type", "observed_at"),
        Index("ix_obs_geo_time", "latitude", "longitude", "observed_at"),
    )


class AlertRecord(Base):
    __tablename__ = "aegis_alerts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    alert_code = Column(String(100), unique=True, nullable=False, index=True)
    hazard_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(50), nullable=False, index=True)  # critical, warning, moderate, minor
    status = Column(String(50), default="active", nullable=False, index=True)  # active, monitoring, resolved, expired
    headline = Column(String(512), nullable=False)
    description = Column(Text, nullable=False)
    instruction = Column(Text, default="", nullable=True)
    
    # Location
    state_name = Column(String(100), default="", nullable=True, index=True)
    district_name = Column(String(100), default="", nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_km = Column(Float, default=50.0, nullable=False)
    geometry_geojson = Column(JSON, default=dict, nullable=True)
    
    # Source & Timing
    source_agency = Column(String(255), nullable=False)
    bulletin_id = Column(String(100), default="", nullable=True)
    published_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    provenance_type = Column(String(50), default="official_warning", nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class AuditLog(Base):
    __tablename__ = "aegis_audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_email = Column(String(255), default="system", nullable=False)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(100), default="", nullable=True)
    details = Column(JSON, default=dict, nullable=False)
    client_ip = Column(String(100), default="127.0.0.1", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)


class ProcessingJob(Base):
    __tablename__ = "aegis_processing_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    data_source_id = Column(String(36), ForeignKey("aegis_data_sources.id", ondelete="CASCADE"), nullable=True, index=True)
    job_type = Column(String(50), default="SCHEDULED_INGESTION", nullable=False)
    status = Column(String(50), default="RECEIVED", nullable=False)  # RECEIVED, PARSING, VALIDATING, NORMALIZING, STORING, COMPLETED, FAILED
    started_at = Column(DateTime(timezone=True), default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Float, default=0.0)
    records_ingested = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)


class SOSSignal(Base):
    __tablename__ = "aegis_sos_signals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    device_id = Column(String(100), nullable=True, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    caller_name = Column(String(100), default="Citizen in Distress", nullable=False)
    caller_phone = Column(String(50), default="", nullable=False)
    emergency_type = Column(String(50), default="general", nullable=False, index=True)  # medical, flood_trapped, fire, building_collapse, cyclone_shelter, general
    severity = Column(String(30), default="CRITICAL", nullable=False)
    status = Column(String(50), default="PENDING_TRIAGE", nullable=False, index=True)  # PENDING_TRIAGE, DISPATCHED, RESPONDER_ON_SCENE, RESCUED, CANCELLED
    
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    accuracy_meters = Column(Float, default=10.0, nullable=True)
    address = Column(String(255), default="", nullable=True)
    city = Column(String(100), default="", nullable=True)
    state = Column(String(100), default="", nullable=True)
    
    battery_percent = Column(Integer, default=100, nullable=True)
    medical_notes = Column(Text, default="", nullable=True)
    casualties_count = Column(Integer, default=1, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class IncidentReport(Base):
    __tablename__ = "aegis_incident_reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), nullable=True, index=True)
    hazard_type = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(30), default="medium", nullable=False)
    
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    location_name = Column(String(255), default="", nullable=True)
    city = Column(String(100), default="", nullable=True)
    state = Column(String(100), default="", nullable=True)
    
    media_urls = Column(JSON, default=list, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False, index=True)
    verification_source = Column(String(100), default="CITIZEN_SUBMISSION", nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)
