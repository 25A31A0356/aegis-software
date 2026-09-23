"""
AEGIS UNIFIED DATA CORE - Database Schema & Data Models
Production PostgreSQL / PostGIS Schema with Time-Series & Observability structures.
"""
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database.base import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "aegis_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="public", nullable=False)  # admin, official, sdrf_officer, public
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class DataSource(Base):
    __tablename__ = "aegis_data_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # imd, cwc, incois, usgs, nasa_firms, open_meteo, cpcb, custom_http
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # WEATHER, EARTHQUAKE, FLOOD, CYCLONE, STORM, LIGHTNING, WILDFIRE, AIR_QUALITY, DISASTER_ALERT, OTHER
    base_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    http_method: Mapped[str] = mapped_column(String(10), default="GET", nullable=False)
    
    # Auth configuration (Secrets encrypted at rest via SecretVault)
    auth_type: Mapped[str] = mapped_column(String(50), default="NONE", nullable=False)  # NONE, API_KEY_QUERY, API_KEY_HEADER, BEARER_TOKEN, BASIC_AUTH
    encrypted_api_key: Mapped[Optional[str]] = mapped_column(Text, default="", nullable=True)
    auth_header_name: Mapped[Optional[str]] = mapped_column(String(100), default="Authorization", nullable=True)
    auth_query_param: Mapped[Optional[str]] = mapped_column(String(100), default="api_key", nullable=True)
    
    # Ingestion Parameters
    request_params: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    request_headers: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    response_format: Mapped[str] = mapped_column(String(20), default="JSON", nullable=False)  # JSON, XML, CSV, GEOJSON
    
    # Scheduling & Execution
    update_frequency_minutes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    cache_duration_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    timeout_seconds: Mapped[float] = mapped_column(Float, default=15.0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Source Health Tracking
    health_status: Mapped[str] = mapped_column(String(50), default="INACTIVE", nullable=False)  # ACTIVE, HEALTHY, DEGRADED, FAILED, INACTIVE
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_response_time_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    field_mappings = relationship("FieldMapping", back_populates="data_source", cascade="all, delete-orphan")
    raw_observations = relationship("RawObservation", back_populates="data_source", cascade="all, delete-orphan")
    normalized_observations = relationship("NormalizedObservation", back_populates="data_source", cascade="all, delete-orphan")


class FieldMapping(Base):
    __tablename__ = "aegis_field_mappings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    data_source_id: Mapped[str] = mapped_column(String(36), ForeignKey("aegis_data_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    external_field_path: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. 'main.temp', 'properties.mag'
    aegis_field_name: Mapped[str] = mapped_column(String(100), nullable=False)     # e.g. 'temperature', 'magnitude'
    source_unit: Mapped[Optional[str]] = mapped_column(String(50), default="standard", nullable=True)
    target_unit: Mapped[Optional[str]] = mapped_column(String(50), default="standard", nullable=True)
    transformation_rule: Mapped[str] = mapped_column(String(100), default="direct", nullable=False)  # direct, kelvin_to_celsius, ms_to_kmh, wmo_code
    confidence: Mapped[str] = mapped_column(String(20), default="HIGH", nullable=False)  # HIGH, MEDIUM, LOW
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    data_source = relationship("DataSource", back_populates="field_mappings")


class RawObservation(Base):
    __tablename__ = "aegis_raw_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    data_source_id: Mapped[str] = mapped_column(String(36), ForeignKey("aegis_data_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    payload_format: Mapped[str] = mapped_column(String(20), default="JSON", nullable=False)
    raw_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    data_source = relationship("DataSource", back_populates="raw_observations")


class NormalizedObservation(Base):
    __tablename__ = "aegis_normalized_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    data_source_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("aegis_data_sources.id", ondelete="SET NULL"), nullable=True, index=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    hazard_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # WEATHER, EARTHQUAKE, FLOOD, CYCLONE, STORM, LIGHTNING, WILDFIRE, AIR_QUALITY
    
    # Geospatial coordinates
    latitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    location_name: Mapped[Optional[str]] = mapped_column(String(255), default="", nullable=True)
    state_name: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True, index=True)
    district_name: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    
    # Timestamps & Freshness
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Assessment & Provenance
    severity: Mapped[str] = mapped_column(String(50), default="moderate", nullable=False)  # minor, moderate, warning, critical
    risk_level: Mapped[str] = mapped_column(String(50), default="MODERATE", nullable=False)  # LOW, MODERATE, HIGH, VERY_HIGH, EXTREME
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    data_type: Mapped[str] = mapped_column(String(50), default="official_observation", nullable=False)  # official_observation, derived, forecast, ai_analysis, cached
    source_authority: Mapped[str] = mapped_column(String(100), default="External Provider", nullable=False)
    processing_version: Mapped[str] = mapped_column(String(20), default="1.0.0", nullable=False)
    
    # Dynamic normalized telemetry measurements
    measurements: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    data_source = relationship("DataSource", back_populates="normalized_observations")

    __table_args__ = (
        Index("ix_obs_hazard_time", "hazard_type", "observed_at"),
        Index("ix_obs_geo_time", "latitude", "longitude", "observed_at"),
    )


class AlertRecord(Base):
    __tablename__ = "aegis_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    alert_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hazard_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # type / hazard classification
    severity: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # critical, warning, moderate, minor
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False, index=True)  # active, monitoring, resolved, expired, draft_pending_approval, cancelled
    headline: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    instruction: Mapped[Optional[str]] = mapped_column(Text, default="", nullable=True)
    
    # Location
    state_name: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True, index=True)
    district_name: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    radius_km: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    geometry_geojson: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict, nullable=True)
    
    # Source & Timing
    source_agency: Mapped[str] = mapped_column(String(255), nullable=False)
    bulletin_id: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Strict 4-Tier Provenance Taxonomy: OFFICIAL_ALERT, SYSTEM_ALERT, COMMUNITY_REPORT, AI_GENERATED_INFO
    provenance_type: Mapped[str] = mapped_column(String(50), default="OFFICIAL_ALERT", nullable=False, index=True)
    
    # AI Authorization Workflow Guardrails (AI must NEVER create official alert without operator promotion)
    is_authorized_official: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    authorized_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    authorized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    authorization_notes: Mapped[Optional[str]] = mapped_column(Text, default="", nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    @property
    def title(self) -> str:
        return self.headline

    @property
    def type(self) -> str:
        return self.hazard_type

    @property
    def source(self) -> str:
        return self.source_agency

    @property
    def expires_at(self) -> Optional[datetime]:
        return self.valid_until


class AuditLog(Base):
    __tablename__ = "aegis_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_email: Mapped[str] = mapped_column(String(255), default="system", nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    details: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    client_ip: Mapped[str] = mapped_column(String(100), default="127.0.0.1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class ProcessingJob(Base):
    __tablename__ = "aegis_processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    data_source_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("aegis_data_sources.id", ondelete="CASCADE"), nullable=True, index=True)
    job_type: Mapped[str] = mapped_column(String(50), default="SCHEDULED_INGESTION", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="RECEIVED", nullable=False)  # RECEIVED, PARSING, VALIDATING, NORMALIZING, STORING, COMPLETED, FAILED
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    records_ingested: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SOSSignal(Base):
    __tablename__ = "aegis_sos_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    device_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    requester_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    caller_name: Mapped[str] = mapped_column(String(100), default="Citizen in Distress", nullable=False)
    caller_phone: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    emergency_type: Mapped[str] = mapped_column(String(50), default="general", nullable=False, index=True)  # medical, flood_trapped, fire, building_collapse, cyclone_shelter, general
    severity: Mapped[str] = mapped_column(String(30), default="CRITICAL", nullable=False, index=True)
    short_message: Mapped[Optional[str]] = mapped_column(String(500), default="", nullable=True)
    
    # State Machine: PENDING, MATCHING, OFFERED, ACCEPTED, RESPONDER_EN_ROUTE, ON_SITE, RESOLVED, CANCELLED, EXPIRED
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False, index=True)
    
    # Geospatial Location
    latitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    accuracy_meters: Mapped[Optional[float]] = mapped_column(Float, default=10.0, nullable=True)
    location_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_location_update: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    address: Mapped[Optional[str]] = mapped_column(String(255), default="", nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    country: Mapped[str] = mapped_column(String(50), default="India", nullable=False)
    
    # Context & Health
    battery_percent: Mapped[Optional[int]] = mapped_column(Integer, default=100, nullable=True)
    medical_notes: Mapped[Optional[str]] = mapped_column(Text, default="", nullable=True)
    casualties_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    # Offline sync & deduplication
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    sync_status: Mapped[str] = mapped_column(String(30), default="SYNCED", nullable=False, index=True)  # SYNCED, SYNC_PENDING
    raw_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Assignment & Lifecycle
    accepted_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, default="", nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


SOSIncident = SOSSignal  # Architectural alias


class SOSResponderCandidate(Base):
    __tablename__ = "aegis_sos_responder_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    sos_id: Mapped[str] = mapped_column(String(36), ForeignKey("aegis_sos_signals.id", ondelete="CASCADE"), nullable=False, index=True)
    responder_user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="OFFERED", nullable=False, index=True)  # OFFERED, ACCEPTED, DECLINED, EXPIRED
    distance_km: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    offered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    selection_rationale: Mapped[Optional[str]] = mapped_column(Text, default="", nullable=True)

    __table_args__ = (
        Index("ix_sos_candidate_unique", "sos_id", "responder_user_id", unique=True),
    )


class SOSAssignment(Base):
    __tablename__ = "aegis_sos_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    sos_id: Mapped[str] = mapped_column(String(36), ForeignKey("aegis_sos_signals.id", ondelete="CASCADE"), nullable=False, index=True)
    responder_user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)  # ACTIVE, COMPLETED, CANCELLED
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    arrived_on_site_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(255), default="", nullable=True)
    
    # Navigation & Route Telemetry
    route_geometry: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)  # GeoJSON LineString
    distance_meters: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    eta_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_responder_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_responder_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_responder_update: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    speed_kmh: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    heading_degrees: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    is_stale_gps: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SOSLocationUpdate(Base):
    __tablename__ = "aegis_sos_location_updates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    sos_id: Mapped[str] = mapped_column(String(36), ForeignKey("aegis_sos_signals.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_type: Mapped[str] = mapped_column(String(20), default="REQUESTER", nullable=False)  # REQUESTER, RESPONDER
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_meters: Mapped[Optional[float]] = mapped_column(Float, default=10.0, nullable=True)
    battery_percent: Mapped[Optional[int]] = mapped_column(Integer, default=100, nullable=True)
    speed_kmh: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class SOSStatusHistory(Base):
    __tablename__ = "aegis_sos_status_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    sos_id: Mapped[str] = mapped_column(String(36), ForeignKey("aegis_sos_signals.id", ondelete="CASCADE"), nullable=False, index=True)
    old_status: Mapped[str] = mapped_column(String(50), nullable=False)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255), default="", nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class SOSNotification(Base):
    __tablename__ = "aegis_sos_notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    sos_id: Mapped[str] = mapped_column(String(36), ForeignKey("aegis_sos_signals.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_type: Mapped[str] = mapped_column(String(30), nullable=False)  # FAMILY_CONTACT, NEARBY_RESPONDER, OPERATOR
    recipient_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(30), default="WEBSOCKET", nullable=False)  # WEBSOCKET, PUSH, SMS, IN_APP
    status: Mapped[str] = mapped_column(String(30), default="SENT", nullable=False)  # PENDING, SENT, DELIVERED, FAILED, ACKNOWLEDGED
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    details: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SafeEvent(Base):
    __tablename__ = "aegis_safe_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    sos_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("aegis_sos_signals.id", ondelete="SET NULL"), nullable=True, index=True)
    user_name: Mapped[str] = mapped_column(String(100), default="Citizen", nullable=False)
    user_phone: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="SAFE", nullable=False, index=True)  # SAFE, RESOLVED, ALL_CLEAR
    message: Mapped[Optional[str]] = mapped_column(String(500), default="I am safe and out of danger.", nullable=True)
    
    # Location
    latitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    accuracy_meters: Mapped[Optional[float]] = mapped_column(Float, default=10.0, nullable=True)
    location_name: Mapped[Optional[str]] = mapped_column(String(255), default="", nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    country: Mapped[str] = mapped_column(String(50), default="India", nullable=False)
    
    # Offline sync & delivery
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    sync_status: Mapped[str] = mapped_column(String(30), default="SYNCED", nullable=False, index=True)  # SYNCED, PENDING_SYNC
    contacts_notified_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class EmergencyContact(Base):
    __tablename__ = "aegis_emergency_contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("aegis_users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    relationship: Mapped[str] = mapped_column(String(50), default="Family", nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_trusted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_on_sos: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_on_safe: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class EmergencyServiceEntity(Base):
    __tablename__ = "aegis_emergency_services"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    service_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # POLICE, AMBULANCE, FIRE, DISASTER_RESPONSE, WOMEN_SAFETY, CHILD_SAFETY, CYBER_CRIME, STATE_DISASTER_MANAGEMENT, NATIONAL_HELPLINE
    phone_numbers: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    alternate_phone: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), default="All India", nullable=True, index=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), default="All Districts", nullable=True, index=True)
    action_types: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["CALL", "SMS", "CONTACT"], nullable=False)  # CALL, SMS, NAVIGATE, CONTACT
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_automated_dispatch_integrated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dispatch_endpoint: Mapped[Optional[str]] = mapped_column(String(1024), default="", nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    display_priority: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class IncidentReport(Base):
    __tablename__ = "aegis_incident_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    anonymous_reporter_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    reporter_name: Mapped[Optional[str]] = mapped_column(String(100), default="Citizen Observer", nullable=True)
    
    # Classification & Category (FLOOD, FIRE, ROAD_BLOCKED, LANDSLIDE, BUILDING_DAMAGE, WATERLOGGING, POWER_FAILURE, MISSING_PERSON, OTHER)
    category: Mapped[str] = mapped_column(String(50), default="OTHER", nullable=False, index=True)
    hazard_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # Backward-compatible synonym
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(30), default="MODERATE", nullable=False, index=True)  # LOW, MODERATE, HIGH, CRITICAL
    
    # Lifecycle & Verification State Machine (SUBMITTED, PENDING_VERIFICATION, VERIFIED, REJECTED, ACTIVE, RESOLVED, EXPIRED)
    status: Mapped[str] = mapped_column(String(50), default="SUBMITTED", nullable=False, index=True)
    verification_status: Mapped[str] = mapped_column(String(50), default="UNVERIFIED", nullable=False, index=True)  # UNVERIFIED, VERIFIED, REJECTED, OFFICIAL
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    verification_source: Mapped[str] = mapped_column(String(100), default="CITIZEN_SUBMISSION", nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="COMMUNITY", nullable=False, index=True)  # COMMUNITY, OFFICIAL
    source_type: Mapped[str] = mapped_column(String(50), default="COMMUNITY_REPORT", nullable=False, index=True)  # Always COMMUNITY_REPORT, never OFFICIAL_ALERT
    
    # Operator Governance & Review
    verified_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(255), default="", nullable=True)
    operator_notes: Mapped[Optional[str]] = mapped_column(Text, default="", nullable=True)
    
    # Cross-Linking to SOS Beacons & Master Incidents
    linked_sos_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    linked_incident_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    
    # Geospatial Location
    latitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    accuracy_meters: Mapped[Optional[float]] = mapped_column(Float, default=10.0, nullable=True)
    location_name: Mapped[Optional[str]] = mapped_column(String(255), default="", nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    country: Mapped[str] = mapped_column(String(50), default="India", nullable=False)
    
    # Media Assets (Photos & Videos)
    media_urls: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    media_type: Mapped[Optional[str]] = mapped_column(String(30), default="NONE", nullable=True)  # PHOTO, VIDEO, MIXED, NONE
    
    # Community Trust Metrics
    upvotes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    downvotes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    
    # Lifecycle Timestamps
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


CommunityReport = IncidentReport  # Architectural alias


class ReportVote(Base):
    __tablename__ = "aegis_report_votes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    report_id: Mapped[str] = mapped_column(String(36), ForeignKey("aegis_incident_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    voter_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # user_id or anonymous device_id
    vote_type: Mapped[str] = mapped_column(String(20), default="UPVOTE", nullable=False)  # UPVOTE, DOWNVOTE
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        Index("ix_report_voter_unique", "report_id", "voter_id", unique=True),
    )


class ActivityEvent(Base):
    __tablename__ = "aegis_activity_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # REPORT_CREATED, REPORT_UPDATED, REPORT_VERIFIED, REPORT_RESOLVED, HAZARD_CREATED, HAZARD_UPDATED, SOS_CREATED, SOS_UPDATED
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # COMMUNITY_REPORT, HAZARD, ALERT, SOS
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(30), default="MODERATE", nullable=False, index=True)
    
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    location_name: Mapped[Optional[str]] = mapped_column(String(255), default="", nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    
    source: Mapped[str] = mapped_column(String(50), default="COMMUNITY", nullable=False)  # OFFICIAL, COMMUNITY
    verification_status: Mapped[str] = mapped_column(String(50), default="UNVERIFIED_COMMUNITY", nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class SafeZone(Base):
    __tablename__ = "aegis_safe_zones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(50), default="RELIEF_SHELTER", nullable=False, index=True)  # RELIEF_SHELTER, EVACUATION_CENTER, MEDICAL_STATION, SAFE_ZONE
    latitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    capacity: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    current_occupancy: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(255), default="", nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), default="", nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    amenities: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)  # ["FOOD", "WATER", "MEDICAL", "POWER"]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class UserPreference(Base):
    __tablename__ = "aegis_user_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("aegis_users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    saved_locations: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)  # [{"name": "Home", "lat": 28.61, "lng": 77.20}]
    hazard_subscriptions: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)  # ["FLOOD", "EARTHQUAKE", "CYCLONE"]
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sms_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    
    # SOS Responder Network Participation
    is_responder_opted_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_known_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    last_known_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    last_location_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=True)
    capabilities: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)  # ["FIRST_AID", "BOAT_RESCUE", "PARAMEDIC", "SEARCH_AND_RESCUE", "FIREFIGHTING"]
    vehicle_type: Mapped[Optional[str]] = mapped_column(String(50), default="MOTORCYCLE", nullable=True)  # AMBULANCE, MOTORCYCLE, 4X4_JEEP, BOAT, ON_FOOT
    max_active_assignments: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    heading_degrees: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speed_kmh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_accuracy_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Family Emergency Contacts
    emergency_contacts: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)  # [{"name": "Family", "phone": "+919876543210", "relationship": "Parent"}]
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class DistrictRegistry(Base):
    """
    AEGIS Pan-India Official Administrative Spatial Registry.
    Contains geospatial coordinates, elevations, and administrative metadata
    for all 28 Indian States, 8 Union Territories, and all 780+ Districts.
    """
    __tablename__ = "aegis_district_registry"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    district_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    state_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(50), default="India", nullable=False)
    is_ut: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    
    # Coordinates & Spatial data
    latitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    elevation_m: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata", nullable=False)
    
    # Metadata & Aliases
    aliases: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("idx_district_state_name", "state_name", "district_name"),
        Index("idx_district_spatial_lat_lng", "latitude", "longitude"),
    )



class DeviceToken(Base):
    """
    Registered mobile and web client device push notification tokens.
    Supports Expo Push, Firebase Cloud Messaging (FCM), and Apple Push Notification Service (APNs).
    """
    __tablename__ = "aegis_device_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    device_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    push_token: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(20), default="ANDROID", nullable=False)  # ANDROID, IOS, WEB
    provider: Mapped[str] = mapped_column(String(20), default="EXPO", nullable=False)     # EXPO, FCM, APNS
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("ix_device_token_user_platform", "user_id", "platform"),
    )


class NotificationDeliveryRecord(Base):
    """
    Authoritative log for all dispatched push notifications, SMS alerts, and in-app emergency signals.
    Strictly tracks provider acceptance, rejection states, and client delivery acknowledgements.
    """
    __tablename__ = "aegis_notification_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # SOS_ASSIGNMENT, SOS_STATUS, CRITICAL_ALERT, REPORT_VERIFICATION
    recipient_type: Mapped[str] = mapped_column(String(30), default="USER", nullable=False)  # CITIZEN, RESPONDER, FAMILY_CONTACT, OPERATOR, BROADCAST
    recipient_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    device_token: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    channel: Mapped[str] = mapped_column(String(30), default="PUSH", nullable=False)  # PUSH, WEBSOCKET, SMS, IN_APP
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    
    # Delivery State Machine: PENDING, DISPATCHED, DELIVERED, REJECTED_BY_PROVIDER, FAILED, ACKNOWLEDGED
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False, index=True)
    provider_response: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Device(Base):
    """
    Physical hardware device registration.
    Tracks OS version, hardware vendor, app version, and links to push tokens.
    """
    __tablename__ = "aegis_devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    device_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("aegis_users.id", ondelete="SET NULL"), nullable=True, index=True)
    platform: Mapped[str] = mapped_column(String(20), default="ANDROID", nullable=False)  # ANDROID, IOS, WEB
    os_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    app_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    device_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ReportEvidence(Base):
    """
    Verified multimedia evidence attached to citizen and responder incident reports.
    Enforces secure hash auditing, size bounds, and MIME safety.
    """
    __tablename__ = "aegis_report_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    report_id: Mapped[str] = mapped_column(String(36), ForeignKey("aegis_incident_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    uploader_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    media_type: Mapped[str] = mapped_column(String(30), default="PHOTO", nullable=False)  # PHOTO, VIDEO, AUDIO, DOCUMENT
    file_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), default="image/jpeg", nullable=False)
    sha256_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ReportVerification(Base):
    """
    Immutable audit log for operator verification reviews of incident reports.
    Records operator decisions, verified severity adjustments, and rationale.
    """
    __tablename__ = "aegis_report_verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    report_id: Mapped[str] = mapped_column(String(36), ForeignKey("aegis_incident_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    operator_id: Mapped[str] = mapped_column(String(36), ForeignKey("aegis_users.id", ondelete="CASCADE"), nullable=False, index=True)
    verification_status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # VERIFIED, REJECTED, UNDER_REVIEW
    verified_severity: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    operator_notes: Mapped[Optional[str]] = mapped_column(Text, default="", nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(255), default="", nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class EmergencyFacility(Base):
    """
    Critical emergency response infrastructure and medical facilities.
    Supports Hospitals, Fire Stations, Police Headquarters, Relief Shelters, and NDRF Bases.
    """
    __tablename__ = "aegis_emergency_facilities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # HOSPITAL, FIRE_STATION, POLICE_STATION, RELIEF_CAMP, NDRF_BASE, DISASTER_HQ
    latitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), default="", nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True, index=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True, index=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), default="", nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    current_occupancy: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    operational_status: Mapped[str] = mapped_column(String(50), default="OPERATIONAL", nullable=False, index=True)  # OPERATIONAL, COMPROMISED, EVACUATED, OFFLINE
    amenities: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)  # ["ICU", "TRAUMA_CENTER", "POWER_BACKUP", "OXYGEN"]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("idx_facility_geo", "latitude", "longitude"),
        Index("idx_facility_type_status", "facility_type", "operational_status"),
    )


class AIDecisionAudit(Base):
    """
    Authoritative audit record for all AI-assisted disaster intelligence tasks.
    Enforces human oversight guardrails: records task, model provider, input hash,
    confidence score, and official human authorization state.
    """
    __tablename__ = "aegis_ai_decision_audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_provider: Mapped[str] = mapped_column(String(100), default="gemini-1.5-flash", nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # CLASSIFICATION, RISK_ASSESSMENT, SUMMARIZATION, HAZARD_EXTRACTION, RESOURCE_RECOMMENDATION
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    input_context: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    
    # Human Authorization Guardrail
    authorization_status: Mapped[str] = mapped_column(String(50), default="NOT_REQUIRED", nullable=False, index=True)  # PENDING_OFFICIAL_REVIEW, AUTHORIZED_OFFICIAL, REJECTED, NOT_REQUIRED
    authorized_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    authorized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    authorization_notes: Mapped[Optional[str]] = mapped_column(Text, default="", nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
