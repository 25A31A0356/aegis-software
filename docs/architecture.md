# AEGIS Unified Data Core — Architecture & Technical Design

## 1. Executive Overview

**AEGIS Unified Data Core** is the central, decoupled, production-grade data backbone for the AEGIS Multi-Hazard Early Warning Platform. It provides a fault-tolerant, extensible pipeline ingesting real-time feeds from national and global meteorological, seismic, hydrological, oceanographic, and satellite monitoring agencies (IMD, CWC, INCOIS, USGS, NASA FIRMS, CPCB, and custom admin-defined REST APIs).

The system addresses the heterogeneity of external scientific data formats by implementing **dynamic heuristic field detection**, **physical unit normalization**, **strict boundary validation**, **spatial-temporal deduplication**, **multi-source hazard correlation**, and **explicit provenance labeling** (`RAW_OBSERVATION` vs `NORMALIZED_OBSERVATION` vs `AI_GENERATED`).

```text
+-------------------------------------------------------------------------------------------------------+
|                                    AEGIS UNIFIED DATA CORE TOPOLOGY                                   |
+-------------------------------------------------------------------------------------------------------+
|                                                                                                       |
|  [ EXTERNAL AUTHORITATIVE FEEDS ]                                                                     |
|  +--------------+  +--------------+  +--------------+  +--------------+  +--------------+             |
|  |   IMD AWS    |  |  CWC Rivers  |  | INCOIS Tsunami| |  USGS Seismic| | NASA FIRMS Sat|             |
|  +-------+------+  +-------+------+  +-------+------+  +-------+------+  +-------+------+             |
|          |                 |                 |                 |                 |                    |
|          v                 v                 v                 v                 v                    |
|  +-------------------------------------------------------------------------------------------------+  |
|  |                                  SSRF GUARD & CIPHER VAULT (AES-256)                            |  |
|  |   * RFC 1918 & Cloud Metadata Filter  * Fernet Decryption at Rest  * Token Redaction Engine     |  |
|  +-------------------------------------------------------------------------------------------------+  |
|                                                  |                                                    |
|                                                  v                                                    |
|  +-------------------------------------------------------------------------------------------------+  |
|  |                                     INGESTION & PARSING ENGINE                                  |  |
|  |   * Heuristic Semantic Field Detector   * Physical Unit Converter (°F->°C, mph->km/h, in->mm)   |  |
|  |   * Telemetry Range & Coordinate Validator   * Haversine Spatial-Temporal Deduplicator         |  |
|  +-------------------------------------------------------------------------------------------------+  |
|                                                  |                                                    |
|                                                  v                                                    |
|  +-------------------------------------------------------------------------------------------------+  |
|  |                             PERSISTENCE & CACHING LAYER (SQLAlchemy 2.0)                        |  |
|  |   * PostgreSQL + PostGIS (Spatial GIST Indexes)   * Redis Cache & Rate Limiting Cluster        |  |
|  +-------------------------------------------------------------------------------------------------+  |
|                                                  |                                                    |
|                                                  v                                                    |
|  +-------------------------------------------------------------------------------------------------+  |
|  |                         MULTI-SOURCE SPATIAL CORRELATION & AI LAYER                             |  |
|  |   * Flood Stage + Rainfall Risk Fusion   * Strict [AI_GENERATED] Provenance Tagging             |  |
|  +-------------------------------------------------------------------------------------------------+  |
|                                                  |                                                    |
|                                                  v                                                    |
|  +-------------------------------------------------------------------------------------------------+  |
|  |                            UNIFIED FASTAPI REST SUITE (/api/v1/...)                             |  |
|  |   * Weather  * Hazards  * Alerts  * Earthquakes  * Floods  * Cyclones  * Admin & Telemetry      |  |
|  +-------------------------------------------------------------------------------------------------+  |
|          |                                                  |                                         |
|          v                                                  v                                         v
|  +-----------------------+                         +-----------------------+              +--------+  |
|  |  AEGIS Web (React 19) |                         |  AEGIS Android / iOS  |              | SDRF/  |  |
|  |  Operator Console     |                         |  Mobile Disaster App  |              | NDMA   |  |
|  +-----------------------+                         +-----------------------+              +--------+  |
+-------------------------------------------------------------------------------------------------------+
```

---

## 2. Core Architectural Pillars

### 2.1 Decoupled Data Pipeline Architecture

The backend is structured into modular layers adhering to clean architecture principles:

1. **Providers Layer (`app/providers/`)**: Standardized adapters implementing the `BaseProvider` interface (`fetch`, `parse`, `normalize`, `validate`).
2. **Ingestion Layer (`app/ingestion/`)**:
   - `detector.py`: Heuristic field classification matching unknown payload structures against domain patterns (e.g. `temp_f`, `wind_dir`, `mag`, `stage_m`).
   - `classifier.py`: Automated hazard category classification (`WEATHER`, `EARTHQUAKE`, `FLOOD`, `CYCLONE`, `WILDFIRE`, `AIR_QUALITY`).
   - `validator.py`: Physics-based range validation (e.g. temperature [-90°C, 60°C], humidity [0%, 100%], coordinates [-90, 90], [-180, 180]).
   - `deduplicator.py`: Spatial-temporal proximity deduplication using the Haversine formula and sliding time windows.
   - `pipeline.py`: Orchestrator executing the complete ETL sequence.
3. **Engines Layer (`app/engines/`)**:
   - `correlation.py`: Multi-source event fusion (combining high river stage telemetry from CWC with heavy precipitation from IMD/Open-Meteo to calculate compound flood risk).
   - `hazard_engine.py`: Dynamic hazard risk level calculation and CAP 1.2 alert triggering.
   - `ai_layer.py`: LLM/AI contextual synthesis with immutable `data_type="AI_GENERATED"` metadata.
4. **Persistence Layer (`app/database/`, `app/cache/`)**:
   - PostgreSQL 16 with PostGIS extension for high-performance spatial querying (`ST_DWithin`, `ST_MakePoint`).
   - Composite B-Tree & GIST indexes on `(hazard_type, timestamp DESC)` and `(latitude, longitude)`.
   - Redis 7.2 with in-memory caching fallback for sub-10ms response times.
5. **Security & Cryptography (`app/core/`)**:
   - `SecretVault`: Fernet AES-128-CBC/SHA256 authenticated encryption for external API tokens stored in PostgreSQL.
   - `SSRFGuard`: Outbound socket verification blocking RFC 1918 subnets, loopbacks, link-local, and AWS/GCP/Azure instance metadata endpoints (`169.254.169.254`).
   - `mask_secret()`: Deterministic masking preserving only the last 4 characters (`****************AB92`).

---

## 3. Data Flow & Provenance Tracking

Every record processed through the Unified Data Core is tagged with its provenance level:

- **`RAW_OBSERVATION`**: Unmodified JSON payload received from the upstream agency, preserved in PostgreSQL `raw_observations` for complete auditability and historical replay.
- **`NORMALIZED_OBSERVATION`**: Synthesized, unit-standardized record adhering to the AEGIS canonical telemetry schema (temperatures in Celsius, speeds in km/h, precipitation in mm, pressures in hPa, coordinates in WGS 84).
- **`AI_GENERATED`**: Synthesized summaries, natural language risk assessments, or predictive hazard advisories generated by AI models. These are strictly segregated from primary telemetry and explicitly labeled to prevent operator confusion.

---

## 4. Background Job Scheduling

The backend runs an asynchronous background scheduler powered by `APScheduler`:

- Dynamically schedules periodic ingestion jobs per active data source based on `ingestion_interval_seconds` (e.g. 60s for seismic, 300s for weather, 600s for river levels).
- Logs execution telemetry (`records_fetched`, `records_normalized`, `records_validated`, `records_deduplicated`, `duration_ms`) into `processing_jobs`.
- Automatically executes exponential backoff on consecutive provider failures.
