# AEGIS Unified Data Core — Data Model & Schema Specifications

## 1. Entity-Relationship Overview

The database uses PostgreSQL 16 with the PostGIS extension for spatial index acceleration, along with composite temporal-spatial indexing.

```
+----------------------------------------------------------------------------------------------------+
|                                    DATABASE ENTITY RELATIONSHIPS                                   |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  +-----------------------+              1:N             +-----------------------+                  |
|  |     data_sources      |----------------------------->|    field_mappings     |                  |
|  |  - id (UUID PK)       |                              |  - id (UUID PK)       |                  |
|  |  - name, code         |                              |  - source_id (FK)     |                  |
|  |  - encrypted_api_key  |                              |  - source_field_path  |                  |
|  |  - base_url           |                              |  - standard_field_name|                  |
|  |  - is_active          |                              |  - source/target_unit |                  |
|  +-----------+-----------+                              +-----------------------+                  |
|              |                                                                                     |
|              | 1:N                                                                                 |
|              +--------------------------------+                                                    |
|              |                                |                                                    |
|              v                                v                                                    |
|  +-----------------------+        +-----------------------+        +-----------------------+       |
|  |   raw_observations    |        |normalized_observations|------->|     alert_records     |       |
|  |  - id (UUID PK)       |        |  - id (UUID PK)       |        |  - id (UUID PK)       |       |
|  |  - source_id (FK)     |        |  - source_id (FK)     |        |  - alert_code (CAP)   |       |
|  |  - raw_payload (JSONB)|        |  - hazard_type        |        |  - severity, urgency  |       |
|  |  - payload_hash       |        |  - lat, lon, geom     |        |  - title, description |       |
|  |  - fetched_at         |        |  - temperature_c      |        |  - affected_geom      |       |
|  +-----------------------+        |  - wind_speed_kmh     |        +-----------------------+       |
|                                   |  - water_level_m      |                                        |
|                                   |  - magnitude, depth_km|                                        |
|                                   |  - data_type (TAG)    |                                        |
|                                   |  - timestamp          |                                        |
|                                   +-----------------------+                                        |
|                                                                                                    |
|  +-----------------------+        +-----------------------+        +-----------------------+       |
|  |    processing_jobs    |        |      audit_logs       |        |         users         |       |
|  |  - id (UUID PK)       |        |  - id (UUID PK)       |        |  - id (UUID PK)       |       |
|  |  - source_id (FK)     |        |  - action, resource   |        |  - email, role        |       |
|  |  - records_fetched    |        |  - actor_id, ip       |        |  - hashed_password    |       |
|  |  - duration_ms        |        |  - details (JSONB)    |        |  - is_active          |       |
|  +-----------------------+        +-----------------------+        +-----------------------+       |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Table Schemas & Column Definitions

### 2.1 `data_sources`
Tracks external telemetry and API endpoints with their configuration and encrypted credentials.
- `id` (`UUID`, PK): Unique source identifier.
- `name` (`VARCHAR(100)`): Human-readable name (e.g. `IMD Radar Doppler Grid`).
- `code` (`VARCHAR(50)`, Unique): Unique machine identifier (e.g. `imd_weather`).
- `hazard_type` (`VARCHAR(30)`): `WEATHER`, `EARTHQUAKE`, `FLOOD`, `CYCLONE`, `WILDFIRE`, `AIR_QUALITY`, `OTHER`.
- `base_url` (`VARCHAR(500)`): HTTP endpoint URL.
- `auth_type` (`VARCHAR(30)`): `NONE`, `API_KEY`, `BEARER`, `CUSTOM_HEADER`.
- `encrypted_api_key` (`TEXT`, Nullable): Fernet-encrypted ciphertext token.
- `headers_json` (`JSONB`): Optional custom headers dictionary.
- `is_active` (`BOOLEAN`): Toggle for background polling.
- `ingestion_interval_seconds` (`INTEGER`): Background polling frequency (default: 300).
- `total_records_ingested` (`INTEGER`): Cumulative count of processed records.

### 2.2 `normalized_observations`
Unified, canonical multi-hazard telemetry table.
- `id` (`UUID`, PK): Primary observation key.
- `source_id` (`UUID`, FK): Originating data source.
- `hazard_type` (`VARCHAR(30)`): Standardized hazard category.
- `external_id` (`VARCHAR(150)`): Upstream provider identifier.
- `location_name` (`VARCHAR(255)`): Place / station name.
- `latitude` (`DOUBLE PRECISION`): WGS 84 Latitude [-90.0, 90.0].
- `longitude` (`DOUBLE PRECISION`): WGS 84 Longitude [-180.0, 180.0].
- `elevation_m` (`DOUBLE PRECISION`): Height in meters above sea level.
- `timestamp` (`TIMESTAMP WITH TIME ZONE`): Observation recorded time.
- **Physical Standard Metrics**:
  - `temperature_c` (`DOUBLE PRECISION`): Metric temperature in Celsius.
  - `humidity_percent` (`DOUBLE PRECISION`): Relative humidity [0% - 100%].
  - `pressure_hpa` (`DOUBLE PRECISION`): Atmospheric pressure in hPa.
  - `wind_speed_kmh` (`DOUBLE PRECISION`): Wind velocity in km/h.
  - `wind_direction_deg` (`DOUBLE PRECISION`): Wind angle [0° - 360°].
  - `precipitation_mm` (`DOUBLE PRECISION`): Total precipitation in mm.
  - `water_level_m` (`DOUBLE PRECISION`): River / reservoir stage in meters.
  - `flow_rate_cumecs` (`DOUBLE PRECISION`): Water discharge in $m^3/s$.
  - `flood_stage` (`VARCHAR(50)`): `NORMAL`, `WARNING`, `DANGER`, `EXTREME`.
  - `magnitude` (`DOUBLE PRECISION`): Richter / moment magnitude.
  - `depth_km` (`DOUBLE PRECISION`): Seismic hypocenter depth in km.
  - `pm25`, `pm10`, `aqi` (`DOUBLE PRECISION`): Air quality metrics.
  - `fire_radiative_power` (`DOUBLE PRECISION`): Satellite thermal MW output.
- `data_type` (`VARCHAR(50)`): `RAW_OBSERVATION`, `NORMALIZED_OBSERVATION`, or `AI_GENERATED`.
- `is_validated` (`BOOLEAN`): Passed physics-based range & coordinate bounds checks.
- `confidence_score` (`DOUBLE PRECISION`): Range [0.0, 1.0].

---

## 3. Database Indexes

```sql
-- Spatial GIST Index (PostGIS)
CREATE INDEX ix_obs_geom ON normalized_observations USING GIST (geom);

-- Composite B-Tree Indexes for Temporal Query Acceleration
CREATE INDEX ix_obs_hazard_time ON normalized_observations (hazard_type, timestamp DESC);
CREATE INDEX ix_obs_lat_lon ON normalized_observations (latitude, longitude);
CREATE INDEX ix_obs_source_time ON normalized_observations (source_id, timestamp DESC);

-- Unique Deduplication Index on External ID + Source
CREATE UNIQUE INDEX uq_obs_source_external ON normalized_observations (source_id, external_id) 
WHERE external_id IS NOT NULL;
```
