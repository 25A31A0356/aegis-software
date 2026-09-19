# AEGIS Mobile Integration Guide — `aegis-alert` (Android & iOS)

This guide documents how the mobile client application ([https://github.com/25A31A0356/aegis-alert](https://github.com/25A31A0356/aegis-alert)) integrates with the **AEGIS Unified Data Core** backend.

---

## 1. Mobile Architecture & Communication Flow

```
+----------------------------------------------------------------------------------------------------+
|                          MOBILE CLIENT (aegis-alert) & DATA CORE TOPOLOGY                          |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|    [ CITIZEN MOBILE APP ]                                                                          |
|    - Android (Kotlin / React Native)                                                               |
|    - iOS (Swift / React Native)                                                                    |
|                                                                                                    |
|          | 1. Periodic Geo-Fence Sync (/api/v1/mobile/sync)                                        |
|          | 2. Distress Beacon Trigger (/api/v1/sos)                                                |
|          | 3. Citizen Incident Report (/api/v1/reports)                                            |
|          | 4. Weather & Hazard Query (/api/v1/weather/current, /api/v1/alerts)                      |
|          v                                                                                         |
|                                                                                                    |
|    [ AEGIS UNIFIED DATA CORE BACKEND (:8000) ]                                                     |
|    - Rate-Limiting & Auth Guard                                                                    |
|    - Haversine Spatial Geo-Fencing                                                                 |
|    - PostGIS Spatial Persistence                                                                   |
|    - Redis In-Memory Speed Cache                                                                   |
|    - SDRF First-Responder Real-Time Dispatch                                                       |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Key Mobile Endpoints

### 2.1 Single-Call Mobile Sync Bundle
**Endpoint**: `GET /api/v1/mobile/sync`

Used on app launch, pull-to-refresh, or background geo-fence transitions to fetch all active threats, nearby emergency alerts, and national helplines in a single, battery-efficient HTTP call.

#### Query Parameters:
- `lat` (float, required): User's current GPS latitude
- `lon` (float, required): User's current GPS longitude
- `radius_km` (float, optional, default: 50.0): Alert search radius

#### Sample Response:
```json
{
  "success": true,
  "data": {
    "nearby_alerts_count": 1,
    "threat_level": "EXTREME",
    "active_alerts": [
      {
        "id": "c71a3d90-...",
        "code": "CAP-DEL-2026-0919-01",
        "headline": "Flash Flood Warning along Yamuna Floodplain",
        "hazard_type": "FLOOD",
        "severity": "critical",
        "instruction": "Evacuate low-lying areas. Move to designated SDRF flood relief centers.",
        "distance_km": 4.2,
        "published_at": "2026-09-19T14:30:00Z"
      }
    ],
    "nearby_hazards": [],
    "emergency_helplines": {
      "National Emergency Number": "112",
      "NDRF Disaster Response": "1078",
      "Disaster Management Services": "108",
      "Ambulance Services": "102",
      "Fire Brigade": "101",
      "Police Emergency": "100"
    },
    "offline_sync_version": "1.0.0"
  },
  "freshness": { "status": "fresh", "age_seconds": 2 }
}
```

---

### 2.2 Submitting an Emergency SOS Distress Beacon
**Endpoint**: `POST /api/v1/sos`

When a citizen presses the Emergency SOS button, the mobile app sends an encrypted distress beacon with GPS coordinates, battery level, and optional medical notes.

#### Request Body:
```json
{
  "caller_name": "Rohan Sharma",
  "caller_phone": "+919876543210",
  "emergency_type": "flood_trapped",
  "severity": "CRITICAL",
  "latitude": 28.6139,
  "longitude": 77.2090,
  "accuracy_meters": 5.0,
  "address": "B-42, Yamuna Bazar",
  "city": "New Delhi",
  "state": "Delhi",
  "battery_percent": 34,
  "medical_notes": "Elderly person with cardiac medication trapped on 1st floor",
  "casualties_count": 2,
  "device_id": "ANDROID_IMEI_OR_UUID_1982"
}
```

#### Response:
```json
{
  "success": true,
  "data": {
    "id": "e9b28f30-...",
    "caller_name": "Rohan Sharma",
    "caller_phone_masked": "+91 ***** 10",
    "emergency_type": "flood_trapped",
    "severity": "CRITICAL",
    "status": "PENDING_TRIAGE",
    "latitude": 28.6139,
    "longitude": 77.2090,
    "created_at": "2026-09-19T15:00:00Z"
  }
}
```

---

### 2.3 Crowdsourced Citizen Damage Reporting
**Endpoint**: `POST /api/v1/reports`

Allows citizens to submit ground-truth reports with photo URLs, severity tags, and incident descriptions.

#### Request Body:
```json
{
  "hazard_type": "FLOOD",
  "title": "Bridge Submerged on NH-44",
  "description": "Water levels exceeding road level by 2 feet. Traffic halted.",
  "severity": "high",
  "latitude": 28.5355,
  "longitude": 77.3910,
  "location_name": "Noida Toll Bridge",
  "city": "Noida",
  "state": "Uttar Pradesh",
  "media_urls": [
    "https://storage.aegis.gov.in/reports/img_991823.jpg"
  ]
}
```

---

## 3. Mobile Client Best Practices

1. **Offline-First Caching**:
   - Cache the response from `/api/v1/mobile/sync` locally in SQLite or MMKV.
   - If the device loses internet connectivity, display cached emergency numbers and offline evacuation checklists.
2. **Exponential Backoff on SOS**:
   - If SOS submission fails due to weak cell signal, queue the beacon in local storage and retry immediately upon network reconnectivity.
3. **Battery-Efficient Location Tracking**:
   - Use geofence region monitoring rather than continuous GPS polling to conserve battery during extended blackout scenarios.
