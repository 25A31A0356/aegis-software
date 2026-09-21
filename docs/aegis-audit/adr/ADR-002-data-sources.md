# ADR 002: Multi-Tier Meteorological & Hazard Ingestion Architecture
**Status:** Approved (Phase 0 Baseline)  
**Date:** 2026-09-21  
**Decider Hat:** Principal Architect / Data Analyst

---

## Context
Accurate disaster warnings save lives, while false or fake alerts cause public panic and alert fatigue. The platform must consume reliable data sources, categorize them by trust tier, and ensure that only verified official agencies can trigger high-severity warning banners.

## Decision
Implement a **Three-Tier Ingestion Architecture**:
1. **`OFFICIAL_IN` (Highest Priority)**: National Disaster Management Authority (NDMA SACHET), India Meteorological Department (IMD), Central Water Commission (CWC), INCOIS.
2. **`OFFICIAL_INTL`**: USGS Earthquake Hazards Program, GDACS.
3. **`MODEL_DERIVED`**: Open-Meteo meteorological numerical models (GFS/ECMWF), OpenAQ.

## Rules & Safeguards
- High-severity "Threat Banners" are restricted exclusively to `OFFICIAL_IN` and `OFFICIAL_INTL` sources.
- Model-derived weather forecasts must always be labeled as *"Forecast"* and include provider attribution.
- Scheduled workers ingest, normalize into Common Alerting Protocol (CAP 1.2) geometries, and cache data with TTL and circuit breakers.
