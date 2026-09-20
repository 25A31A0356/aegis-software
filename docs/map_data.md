# AEGIS Unified Geospatial Map Data Specification

Aegis Software serves as the central GIS server for **Aegis Web** (MapLibre / Leaflet / Mapbox GL) and **Aegis Alert Mobile App** (React Native Maps / Expo Mapbox).

---

## 1. Unified Map Data Endpoint: `GET /api/v1/map-data`

### Query Parameters

- `layers`: Comma-separated list (`hazards`, `reports`, `sos_beacons`, `shelters`, `road_hazards`, `all`)
- `bbox`: Spatial bounding box filter in `minLon,minLat,maxLon,maxLat` format (e.g. `68.0,6.0,97.5,37.0`)
- `lat`, `lon` / `lng`: Center coordinate filter
- `radius_km`: Proximity radius in kilometers (default `200.0`)
- `category`: Category filter (`FLOOD`, `EARTHQUAKE`, `FIRE`, `ALL`)

### Response Format: Standard GeoJSON FeatureCollection

```json
{
  "success": true,
  "data": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "id": "rep_99e7c8d6",
        "geometry": {
          "type": "Point",
          "coordinates": [77.2090, 28.6139]
        },
        "properties": {
          "layer": "reports",
          "entity_id": "rep_99e7c8d6",
          "title": "Severe Waterlogging Underpass",
          "category": "FLOOD",
          "severity": "HIGH",
          "source": "COMMUNITY",
          "verification_status": "VERIFIED_COMMUNITY",
          "is_verified": true,
          "upvotes": 5,
          "city": "New Delhi",
          "state": "Delhi",
          "icon": "community_flood"
        }
      },
      {
        "type": "Feature",
        "id": "haz_eq_us7000tijf",
        "geometry": {
          "type": "Point",
          "coordinates": [89.2243, 32.0711]
        },
        "properties": {
          "layer": "hazards",
          "title": "Official Earthquake Observation (M 4.5)",
          "category": "EARTHQUAKE",
          "severity": "WARNING",
          "source": "OFFICIAL",
          "verification_status": "OFFICIAL",
          "icon": "hazard_earthquake"
        }
      }
    ],
    "layer_summary": {
      "hazards": 12,
      "reports": 8,
      "sos_beacons": 2,
      "shelters": 4,
      "road_hazards": 3
    },
    "generated_at": "2026-09-19T18:00:00.000Z"
  }
}
```

---

## 2. Mapping Provider Keys & Restrictions

| Provider | Purpose | Key Type | Server vs Client | Restrictions |
| :--- | :--- | :--- | :--- | :--- |
| **OpenStreetMap / CARTO** | Base Map Tiles | Public / Open | Client (Web & Mobile) | None / Free open attribution |
| **MapLibre GL / Vector Tiles** | Web Vector Rendering | Open Source | Client (Web) | Self-hosted or open styles |
| **Mapbox** (Optional) | Satellite Imagery & Elevation | Restricted Client Key | Client (Mobile) | Domain restricted to `*.aegis.gov.in` / Bundle ID `in.gov.aegis.alert` |
| **Google Maps SDK** (Optional) | Mobile Navigation fallback | Restricted API Key | Client (Mobile) | Android SHA-1 fingerprint & iOS Bundle ID restricted |

*Note: Private scientific provider keys (NASA FIRMS, USGS, IMD) remain strictly on Aegis Software backend and are NEVER transmitted to client map SDKs.*
