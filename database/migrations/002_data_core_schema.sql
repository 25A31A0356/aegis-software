-- ============================================================================
-- AEGIS UNIFIED DATA CORE: Central Data Gateway Tables & PostGIS Indexes
-- Migration: 002_data_core_schema.sql
-- ============================================================================

-- 1. Table: aegis_data_sources (Provider Registry & Encrypted Secret Vault)
CREATE TABLE IF NOT EXISTS aegis_data_sources (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    provider_code VARCHAR(50) NOT NULL,
    category VARCHAR(50) NOT NULL,
    base_url VARCHAR(1024) NOT NULL,
    endpoint VARCHAR(1024) NOT NULL DEFAULT '',
    http_method VARCHAR(10) NOT NULL DEFAULT 'GET',
    auth_type VARCHAR(50) NOT NULL DEFAULT 'NONE',
    encrypted_api_key TEXT DEFAULT '',
    auth_header_name VARCHAR(100) DEFAULT 'Authorization',
    auth_query_param VARCHAR(100) DEFAULT 'api_key',
    request_params JSONB NOT NULL DEFAULT '{}'::jsonb,
    request_headers JSONB NOT NULL DEFAULT '{}'::jsonb,
    response_format VARCHAR(20) NOT NULL DEFAULT 'JSON',
    update_frequency_minutes INT NOT NULL DEFAULT 5,
    cache_duration_seconds INT NOT NULL DEFAULT 300,
    timeout_seconds NUMERIC(6, 2) NOT NULL DEFAULT 15.0,
    max_retries INT NOT NULL DEFAULT 3,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    health_status VARCHAR(50) NOT NULL DEFAULT 'INACTIVE',
    consecutive_failures INT NOT NULL DEFAULT 0,
    last_success_at TIMESTAMP WITH TIME ZONE,
    last_failure_at TIMESTAMP WITH TIME ZONE,
    last_response_time_ms NUMERIC(8, 2) NOT NULL DEFAULT 0.0,
    last_http_status INT,
    last_error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_data_sources_code ON aegis_data_sources(provider_code);
CREATE INDEX IF NOT EXISTS idx_data_sources_category ON aegis_data_sources(category);
CREATE INDEX IF NOT EXISTS idx_data_sources_health ON aegis_data_sources(health_status);

-- 2. Table: aegis_field_mappings
CREATE TABLE IF NOT EXISTS aegis_field_mappings (
    id VARCHAR(36) PRIMARY KEY,
    data_source_id VARCHAR(36) NOT NULL REFERENCES aegis_data_sources(id) ON DELETE CASCADE,
    external_field_path VARCHAR(255) NOT NULL,
    aegis_field_name VARCHAR(100) NOT NULL,
    source_unit VARCHAR(50) DEFAULT 'standard',
    target_unit VARCHAR(50) DEFAULT 'standard',
    transformation_rule VARCHAR(100) NOT NULL DEFAULT 'direct',
    confidence VARCHAR(20) NOT NULL DEFAULT 'HIGH',
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_field_mappings_source ON aegis_field_mappings(data_source_id);

-- 3. Table: aegis_raw_observations (Immutable Provider Audit Trail)
CREATE TABLE IF NOT EXISTS aegis_raw_observations (
    id VARCHAR(36) PRIMARY KEY,
    data_source_id VARCHAR(36) NOT NULL REFERENCES aegis_data_sources(id) ON DELETE CASCADE,
    source_record_id VARCHAR(255),
    payload_format VARCHAR(20) NOT NULL DEFAULT 'JSON',
    raw_payload JSONB NOT NULL,
    received_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_raw_obs_source ON aegis_raw_observations(data_source_id);
CREATE INDEX IF NOT EXISTS idx_raw_obs_time ON aegis_raw_observations(received_at DESC);

-- 4. Table: aegis_normalized_observations (Multi-Hazard Spatial Telemetry)
CREATE TABLE IF NOT EXISTS aegis_normalized_observations (
    id VARCHAR(36) PRIMARY KEY,
    data_source_id VARCHAR(36) REFERENCES aegis_data_sources(id) ON DELETE SET NULL,
    source_record_id VARCHAR(255),
    hazard_type VARCHAR(50) NOT NULL,
    latitude NUMERIC(10, 7) NOT NULL,
    longitude NUMERIC(10, 7) NOT NULL,
    geom GEOMETRY(Point, 4326),
    location_name VARCHAR(255) DEFAULT '',
    state_name VARCHAR(100) DEFAULT '',
    district_name VARCHAR(100) DEFAULT '',
    observed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    received_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_until TIMESTAMP WITH TIME ZONE,
    severity VARCHAR(50) NOT NULL DEFAULT 'moderate',
    risk_level VARCHAR(50) NOT NULL DEFAULT 'MODERATE',
    confidence NUMERIC(4, 2) NOT NULL DEFAULT 1.0,
    data_type VARCHAR(50) NOT NULL DEFAULT 'official_observation',
    source_authority VARCHAR(100) NOT NULL DEFAULT 'External Provider',
    processing_version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    measurements JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_norm_obs_geom ON aegis_normalized_observations USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_norm_obs_hazard_time ON aegis_normalized_observations(hazard_type, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_norm_obs_state ON aegis_normalized_observations(state_name);

-- 5. Table: aegis_audit_logs
CREATE TABLE IF NOT EXISTS aegis_audit_logs (
    id VARCHAR(36) PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL DEFAULT 'system',
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id VARCHAR(100) DEFAULT '',
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    client_ip VARCHAR(100) NOT NULL DEFAULT '127.0.0.1',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON aegis_audit_logs(action, created_at DESC);

-- 6. Table: aegis_processing_jobs
CREATE TABLE IF NOT EXISTS aegis_processing_jobs (
    id VARCHAR(36) PRIMARY KEY,
    data_source_id VARCHAR(36) REFERENCES aegis_data_sources(id) ON DELETE CASCADE,
    job_type VARCHAR(50) NOT NULL DEFAULT 'SCHEDULED_INGESTION',
    status VARCHAR(50) NOT NULL DEFAULT 'RECEIVED',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms NUMERIC(10, 2) DEFAULT 0.0,
    records_ingested INT DEFAULT 0,
    records_failed INT DEFAULT 0,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_source_status ON aegis_processing_jobs(data_source_id, status);
