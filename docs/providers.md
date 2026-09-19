# AEGIS Unified Data Core — Authoritative Data Providers & Connectors

## 1. Provider Registry & Adapter Ecosystem

The Unified Data Core includes built-in adapters for key national and global scientific telemetry networks, plus an extensible generic REST adapter for administrator-registered sensors.

| Provider Code | Agency Name | Domain | Primary Metrics | Default Poll Interval | Auth Method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `open_meteo` | Open-Meteo / WMO Global | Meteorological | Temp (°C), Wind (km/h), Rain (mm), Pressure (hPa), Humidity (%) | 300s (5 min) | None (Open Data) |
| `usgs_earthquakes` | USGS Earthquake Hazards Program | Seismic | Magnitude, Depth (km), Epicenter Coordinates, Tsunami Flag | 60s (1 min) | None (Open GeoJSON) |
| `imd_weather` | India Meteorological Department (IMD) | Weather / Cyclones | AWS Station Observations, Radar Reflectivity, Monsoon Warnings | 300s (5 min) | API Key / Token |
| `cwc_floods` | Central Water Commission (CWC India) | Hydrological | River Level (m), Discharge (cumecs), Danger Level, Flood Warning Stage | 600s (10 min) | API Key / Token |
| `incois_ocean` | INCOIS (Indian National Ocean Information) | Oceanographic | Tsunami Warning, Wave Height (m), Sea Surface Temp (°C), Cyclone Surge | 300s (5 min) | Token / Open OGC |
| `nasa_firms` | NASA FIRMS (MODIS / VIIRS Satellites) | Thermal Wildfires | Active Fire Coordinates, Fire Radiative Power (MW), Detection Confidence | 900s (15 min) | MAP_KEY |
| `cpcb_aqi` | Central Pollution Control Board (CPCB) | Air Quality | AQI, PM2.5, PM10, NO2, SO2, CO, O3 | 600s (10 min) | Data.gov.in API Key |
| `custom_http` | Custom Administrator REST Feeds | Multi-Hazard | Dynamic JSON payload parsed via semantic field detector & unit rules | Custom (30s - 86400s) | Header / Bearer / Key |

---

## 2. Dynamic Field Detection & Unit Normalization

When an external provider is polled or registered via the Admin Console, the **Heuristic Field Detector** parses sample records and infers standard mappings:

### Semantic Field Matching Patterns
- **Temperature**: `r"(temp|temperature|temp_c|temp_f|t2m|air_temp|dry_bulb)"` $\to$ `temperature_c`
- **Wind Speed**: `r"(wind_speed|wind_spd|wind_velocity|wspd|wind_kph|wind_mph|wind_ms)"` $\to$ `wind_speed_kmh`
- **Precipitation**: `r"(precip|precipitation|rain|rainfall|rain_mm|rain_in|prcp)"` $\to$ `precipitation_mm`
- **Pressure**: `r"(press|pressure|baro|barometer|slp|mslp|surf_press|pressure_hpa|pressure_pa)"` $\to$ `pressure_hpa`
- **River Water Level**: `r"(water_level|gauge_height|river_stage|stage_m|level_m|water_depth)"` $\to$ `water_level_m`
- **Seismic Magnitude**: `r"(mag|magnitude|richter|eq_mag|mag_val)"` $\to$ `magnitude`
- **Air Quality / Particulates**: `r"(pm25|pm2_5|pm_2_5|pm10|pm_10|aqi|air_quality_index)"` $\to$ `pm25`, `pm10`, `aqi`
- **Thermal Fire Power**: `r"(frp|fire_power|fire_radiative_power|thermal_mw)"` $\to$ `fire_radiative_power`

### Physical Unit Conversions Applied
All metrics are stored internally in standard SI / scientific units:
- **Temperature**:
  - Fahrenheit $\to$ Celsius: $T_C = (T_F - 32) \times \frac{5}{9}$
  - Kelvin $\to$ Celsius: $T_C = T_K - 273.15$
- **Speed**:
  - Miles/hour $\to$ km/h: $v_{kmh} = v_{mph} \times 1.60934$
  - Meters/second $\to$ km/h: $v_{kmh} = v_{ms} \times 3.6$
  - Knots $\to$ km/h: $v_{kmh} = v_{kts} \times 1.852$
- **Precipitation**:
  - Inches $\to$ mm: $P_{mm} = P_{in} \times 25.4$
- **Pressure**:
  - Pascals $\to$ hPa: $p_{hPa} = p_{Pa} / 100.0$
  - Atmospheres $\to$ hPa: $p_{hPa} = p_{atm} \times 1013.25$
  - inHg $\to$ hPa: $p_{hPa} = p_{inHg} \times 33.8639$

---

## 3. Registering a New Provider via REST API

```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ADMIN_JWT_TOKEN>" \
  -d '{
    "name": "State Flood Sensor Network",
    "code": "kerala_flood_sensors",
    "hazard_type": "FLOOD",
    "base_url": "https://api.disaster.kerala.gov.in/v2/telemetry",
    "auth_type": "API_KEY",
    "api_key": "KL_SDRF_SECURE_TOKEN_9921",
    "ingestion_interval_seconds": 180,
    "verify_ssl": true
  }'
```
The API key is encrypted using AES-256 Fernet before being written to PostgreSQL and is never logged in plaintext.
