# AEGIS Central Data Gateway — API Specification & Client Contracts

Version: `v1.0.0`  
Base URL: `http://localhost:8000/api/v1` (or production hostname)

The **AEGIS Central Data Gateway** is the single controlled backend between third-party scientific data providers and both **Aegis Web** and **Aegis Alert Mobile App**.

---

## 1. Security & Authentication Architecture

### Client Identification Headers

Clients must pass the `X-Aegis-Client` header to identify client platform context:

- `X-Aegis-Client: web` (Aegis Web Dashboard)
- `X-Aegis-Client: app` (Aegis Alert Mobile Application)
- `X-Aegis-Client: internal` (Automated Ingestion Workers)

### Administrative Authentication

Administrative and sensor configuration routes require a Bearer JWT Token in the standard header:

`Authorization: Bearer <JWT_TOKEN>`

### Zero Client Credential Exposure

- Provider API keys (NASA FIRMS, IMD, CWC, CPCB) exist **strictly on the backend**.
- Client requests never receive provider tokens, database connection strings, or backend secrets.
- All errors are sanitized to prevent stack trace or path disclosure.

---

## 2. Standard Response Wrapper

Every endpoint returns a unified JSON envelope:

```json
{
  "success": true,
  "data": { ... },
  "freshness": {
    "status": "fresh | stale | cached",
    "age_seconds": 12,
    "last_updated": "2026-09-19T14:30:00Z"
  },
  "provenance": {
    "data_type": "official_observation | forecast | spatial_proximity_query",
    "source_authority": "Open-Meteo & IMD Telemetry Network",
    "processing_version": "1.0.0"
  },
  "error": null
}
```

---

## 3. Endpoints Directory

| Endpoint | Method | Client Target | Auth | Description |
| :--- | :--- | :--- | :--- | :--- |
| `/health` | GET | All / Orchestrators | Public | Top-level container liveness & DB/Redis probe |
| `/api/v1/health` | GET | Admin / Monitor | Public | Detailed infrastructure & provider health matrix |
| `/api/v1/status` | GET | Web / App / Admin | Public | Live status of all 8 provider adapters & latencies |
| `/api/v1/weather` | GET | Web / App | Rate Limited | Real-time meteorological observations for coordinates |
| `/api/v1/forecast` | GET | Web / App | Rate Limited | Multi-day daily & 24h hourly forecast curves |
| `/api/v1/hazards` | GET | Web / App | Rate Limited | Filtered multi-hazard observation catalogue |
| `/api/v1/hazards/nearby` | GET | Web / App | Rate Limited | Proximity-sorted hazards with distance & bearing |
| `/api/v1/earthquakes` | GET | Web / App | Rate Limited | Live USGS seismic events & depth metrics |
| `/api/v1/floods` | GET | Web / App | Rate Limited | CWC river water levels, danger stages, & trends |
| `/api/v1/wildfires` | GET | Web / App | Rate Limited | NASA FIRMS VIIRS/MODIS thermal anomalies |
| `/api/v1/alerts` | GET | Web / App | Rate Limited | Official CAP-CP emergency alerts & instructions |
| `/api/v1/location` | GET | Web / App | Rate Limited | Combined geocoding and reverse geocoding resolver |
| `/api/v1/location/search` | GET | Web / App | Rate Limited | Forward geocoding place search |
| `/api/v1/location/reverse` | GET | Web / App | Rate Limited | Reverse geocode coordinates to district & state |
| `/api/v1/mobile/sync` | GET | App (Mobile) | Rate Limited | Single-call low-bandwidth payload for mobile sync |
| `/api/v1/sos` | POST/GET | Web / App | Rate Limited | Distress trigger & list active SOS emergencies |
| `/api/v1/sos/nearby` | GET | Web / App | Rate Limited | Geospatial nearby SOS discovery (10km-20km) |
| `/api/v1/sos/{id}` | GET | Web / App | Rate Limited | Get detailed SOS status, responder, and ETA |
| `/api/v1/sos/{id}/accept` | POST | Web / App | Rate Limited | Atomic responder acceptance (locks assignment) |
| `/api/v1/sos/{id}/decline` | POST | Web / App | Rate Limited | Decline responder offer |
| `/api/v1/sos/{id}/location` | POST | Web / App | Rate Limited | Requester live GPS breadcrumbs |
| `/api/v1/sos/{id}/responder-location` | POST | Web / App | Rate Limited | Responder live GPS breadcrumbs & auto reroute (>150m) |
| `/api/v1/sos/{id}/status` | POST | Web / App | Rate Limited | Update state machine status (e.g. ON_SITE) |
| `/api/v1/sos/{id}/resolve` | POST | Web / App | Rate Limited | Mark emergency as RESOLVED with audit notes |
| `/api/v1/sos/{id}/cancel` | POST | Web / App | Rate Limited | Cancel distress signal |
| `/api/v1/sos/responder/profile` | POST | Web / App | Rate Limited | Update responder opt-in and live availability |
| `/api/v1/reports` | GET/POST | Web / App | Rate Limited | Single Source of Truth Community Incident Reports & Offline Sync |
| `/api/v1/reports/{id}/vote` | POST | Web / App | Rate Limited | Community verification upvote/downvote casting |
| `/api/v1/activity` | GET | Web / App | Rate Limited | Unified Activity Feed merging official & community events |
| `/api/v1/activity/stream` | GET | Web / App | Rate Limited | Server-Sent Events (SSE) live activity event stream |
| `/api/v1/map-data` | GET | Web / App | Rate Limited | Unified GeoJSON GIS map layers (hazards, reports, SOS, shelters) |
| `/api/v1/ws` | WebSocket | Web / App | Client Key | Real-Time bidirectional WebSocket push notifications |
| `/api/v1/ws/sos` | WebSocket | Web / App | Client Key | Dedicated real-time SOS tracking & offer WebSocket |
| `/api/v1/auth/preferences` | GET/PUT | Web / App | Bearer JWT | Cross-platform user saved locations & alert preferences sync |
| `/api/v1/sources` | GET/POST | Admin Console | Admin JWT | External provider connector management & keys |

> **Full SOS Documentation**: See [sos_responder_network.md](file:///c:/Users/tst20/Aegis%20software/docs/sos_responder_network.md) for detailed state machine diagrams, privacy protocols, and event payloads.

---

## 4. Endpoint Specifications & Contracts

### [A] Real-Time Weather (`GET /api/v1/weather`)

**Parameters**:

- `lat` (float, required, e.g. `19.0760`)
- `lng` (float, required, e.g. `72.8777`)
- `city` (string, optional)

**Response Example**:

```json
{
  "success": true,
  "data": {
    "city_name": "Mumbai",
    "state_name": "Maharashtra",
    "coordinates": [19.0760, 72.8777],
    "observed_at": "2026-09-19T14:00:00Z",
    "condition": "Passing Rain Showers",
    "condition_code": "rain",
    "temperature": 29.5,
    "feels_like": 33.2,
    "humidity": 78.0,
    "wind_speed": 16.5,
    "wind_direction": "SW",
    "rain_probability": 75.0,
    "rainfall_expected_mm": 12.4,
    "uv_index": 5.0,
    "barometric_pressure_hpa": 1009.0,
    "visibility_km": 7.5,
    "air_quality_index": 62.0,
    "air_quality_status": "Moderate",
    "source": "Open-Meteo & IMD Telemetry Network",
    "provenance_type": "official_observation",
    "freshness_status": "fresh"
  }
}
```

---

### [B] Weather Forecast (`GET /api/v1/forecast`)

**Parameters**:

- `lat` (float, default `19.0760`)
- `lng` (float, default `72.8777`)
- `days` (int, default `7`, max `16`)

**Response Highlights**:

- `daily`: Array of 7-day high/low temperatures, precipitation sums, rain probability, wind peaks, UV index, weather conditions, sunrise/sunset.
- `hourly`: Array of 24-hour hourly temperatures, apparent temp, humidity, precipitation probability, and wind speeds.
- `severe_weather_warning`: Populated if heavy storms, cyclones, or extreme heatwaves are predicted.

---

### [C] Nearby Hazards (`GET /api/v1/hazards/nearby`)

**Parameters**:

- `lat` (float, required)
- `lng` (float, required)
- `radius_km` (float, default `50.0`)
- `hazard_type` (string, optional: `WEATHER`, `EARTHQUAKE`, `FLOOD`, `WILDFIRE`, `CYCLONE`, `LIGHTNING`)
- `limit` (int, default `30`)

**Response Example**:

```json
{
  "success": true,
  "data": [
    {
      "id": "OBS-FL-902",
      "type": "flood",
      "severity": "CRITICAL",
      "title": "CRITICAL FLOOD Activity at Godavari Basin",
      "description": "Active flood telemetry detected at Godavari Basin, 14.2 km from your location.",
      "distance_km": 14.2,
      "bearing_degrees": 42.5,
      "location": {
        "latitude": 19.1820,
        "longitude": 72.9640,
        "name": "Godavari Basin Gauge",
        "district": "Thane",
        "state": "Maharashtra",
        "country": "India"
      },
      "measurements": {
        "water_level_m": 48.6,
        "danger_level_m": 48.0,
        "trend": "RISING"
      },
      "timestamp": "2026-09-19T13:45:00Z",
      "expires_at": "2026-09-19T19:45:00Z",
      "source": "Central Water Commission (CWC)",
      "confidence": 0.95,
      "status": "ACTIVE"
    }
  ]
}
```

---

### [D] Geographic Location Engine (`GET /api/v1/location`)

**Search Mode**: `GET /api/v1/location/search?query=Bhubaneswar`

- Returns matching cities, districts, states, coordinates, elevation, and timezones.

**Reverse Mode**: `GET /api/v1/location/reverse?lat=20.2961&lng=85.8245`

- Resolves coordinates to district (Khurda), state (Odisha), elevation, and confidence score.

---

### [E] Provider & Platform Status (`GET /api/v1/status`)

**Response Highlights**:

- `platform_status`: `OPERATIONAL | DEGRADED | CRITICAL`
- `active_providers_count`: Number of active provider adapters.
- `providers`: Array detailing each of the 8 providers (`status`, `last_success`, `last_failure`, `last_update`, `latency_ms`, `error_state`, `fallback_active`).

---

## 5. Web & App Integration Contracts

### Aegis Web Contract

- Web queries `/api/v1/weather`, `/api/v1/forecast`, `/api/v1/hazards`, `/api/v1/hazards/nearby`, `/api/v1/alerts`, `/api/v1/location`, and `/api/v1/status`.
- Passes `X-Aegis-Client: web`.
- Displays real-time map overlays, multi-hazard gauges, weather graphs, and emergency bulletins.

### Aegis Alert Mobile App Contract

- Mobile queries `/api/v1/mobile/sync?lat=...&lon=...&radius_km=50` for single-request low-bandwidth synchronization.
- Submits distress signals to `POST /api/v1/sos` and reports to `POST /api/v1/reports`.
- Passes `X-Aegis-Client: app`.
- Utilizes offline emergency helplines bundled in `/mobile/sync` when connectivity is lost.
