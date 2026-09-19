# AEGIS Unified Data Core — REST API v1 Reference

All Unified Data Core endpoints are versioned under `/api/v1/`.

## 1. System & Health Endpoints

### `GET /api/v1/health`
Returns system status, database connectivity, Redis cache latency, and scheduler uptime.

#### Response `200 OK`:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-09-19T14:30:00Z",
  "database": "connected",
  "redis": "connected",
  "sources_active": 7
}
```

---

## 2. Telemetry & Observation Endpoints

### `GET /api/v1/weather/current`
Get normalized real-time weather observations for given coordinates.

#### Query Parameters:
- `lat` (float, required): Latitude [-90.0, 90.0]
- `lon` (float, required): Longitude [-180.0, 180.0]

#### Response `200 OK`:
```json
{
  "location_name": "New Delhi, India",
  "latitude": 28.6139,
  "longitude": 77.2090,
  "timestamp": "2026-09-19T14:00:00Z",
  "temperature_c": 31.4,
  "humidity_percent": 68.0,
  "pressure_hpa": 1008.2,
  "wind_speed_kmh": 14.5,
  "wind_direction_deg": 120.0,
  "precipitation_mm": 0.0,
  "data_type": "NORMALIZED_OBSERVATION",
  "is_validated": true
}
```

### `GET /api/v1/hazards/observations`
Query filtered multi-hazard normalized telemetry.

#### Query Parameters:
- `hazard_type` (string, optional): `WEATHER`, `EARTHQUAKE`, `FLOOD`, `CYCLONE`, `WILDFIRE`, `AIR_QUALITY`
- `min_lat`, `max_lat`, `min_lon`, `max_lon` (float, optional): Bounding box filter
- `limit` (int, default: 50): Number of records to return

---

## 3. Multi-Hazard Specific Endpoints

- `GET /api/v1/earthquakes`: USGS and IMD seismic events with Richter magnitude, hypocenter depth, and tsunami risk flag.
- `GET /api/v1/floods`: CWC hydrological river telemetry, discharge rates in cumecs, and flood danger stages.
- `GET /api/v1/cyclones`: Atmospheric storm tracks, central pressure, and maximum sustained wind speeds.
- `GET /api/v1/wildfires`: NASA FIRMS thermal satellite hotspots and fire radiative power in MW.
- `GET /api/v1/air-quality`: CPCB real-time AQI and particulate concentration ($PM_{2.5}$, $PM_{10}$).
- `GET /api/v1/correlation`: Spatial-temporal multi-hazard risk fusion (e.g. Heavy Rain + River Stage).

---

## 4. Mobile Client & Citizen Safety Endpoints (`aegis-alert`)

Designed for direct consumption by the mobile application ([https://github.com/25A31A0356/aegis-alert](https://github.com/25A31A0356/aegis-alert)):

- `GET /api/v1/mobile/sync`: Single-call battery-efficient bundle returning active local alerts, danger level, local hazards, and national emergency helplines.
- `POST /api/v1/sos`: Submit real-time citizen distress beacons with GPS coordinates, battery status, medical notes, and casualty count.
- `GET /api/v1/sos`: Active SOS signals feed for SDRF first-responder dispatch command center.
- `POST /api/v1/reports`: Crowdsourced citizen incident and damage report intake with photo URLs.
- `GET /api/v1/reports`: List verified and unverified citizen disaster ground-truth reports.

---

## 5. Administrative & Data Source Management

- `GET /api/v1/sources`: List all registered sources with masked API keys (`****************AB92`).
- `POST /api/v1/sources`: Register a new external data feed with Fernet-encrypted credentials.
- `POST /api/v1/sources/{source_id}/trigger`: Trigger immediate manual ingestion pipeline execution.
- `POST /api/v1/sources/test`: Run SSRF-guarded live testing, field detection, and unit preview.
- `GET /api/v1/sources/{source_id}/mappings`: Retrieve visual field mappings.
- `POST /api/v1/sources/{source_id}/mappings`: Update field transformation rules.
- `GET /api/v1/admin/stats`: Get unified system and telemetry metrics.
- `GET /api/v1/admin/audit-logs`: Immutable audit log ledger.
- `GET /api/v1/admin/jobs`: Background ingestion job history.

