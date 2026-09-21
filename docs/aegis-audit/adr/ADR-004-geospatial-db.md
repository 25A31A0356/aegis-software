# ADR 004: Geospatial Database Engine (PostgreSQL + PostGIS)
**Status:** Approved (Phase 0 Baseline)  
**Date:** 2026-09-21  
**Decider Hat:** Principal Architect / Data Analyst

---

## Context
The platform requires rapid spatial queries: finding responders within a 10km radius of an SOS, matching user coordinates against hazard polygons, and aggregating citizen incident reports by administrative district.

## Decision
Standardize on **PostgreSQL 16 + PostGIS 3.4** using the standard spatial reference system **WGS 84 (EPSG:4326)** and `geography(Point, 4326)` columns with GiST spatial indexing.

## Query Strategy
- Responder search: `ST_DWithin(r.location, ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography, 10000)`
- Hazard polygon containment: `ST_Contains(h.geometry, ST_SetSRID(ST_MakePoint(lng, lat), 4326))`
