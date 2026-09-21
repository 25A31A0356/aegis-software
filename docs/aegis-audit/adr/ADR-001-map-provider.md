# ADR 001: Selection of Primary Map, Geocoding & Satellite Provider
**Status:** Approved (Phase 0 Baseline)  
**Date:** 2026-09-21  
**Decider Hat:** Principal Architect / GIS & Realtime Engineer

---

## Context
AEGIS ALERT requires an interactive, high-reliability mapping engine capable of displaying Indian territory with official boundary compliance, high-resolution satellite imagery, typo-tolerant district/locality geocoding, and real-time road routing from responders to victims.

## Options Evaluated
1. **Google Maps Platform**: Industry-standard satellite coverage across India, accurate Directions API for road routing, official boundary rendering, comprehensive SDKs for React and React Native.
2. **MapMyIndia (Mappls)**: Deep house-level Indian geocoding, official national map compliance, but higher enterprise licensing friction and varying satellite recency.
3. **MapLibre GL + OpenStreetMap / MapTiler**: Cost-effective open-source stack, but requires self-hosted tile infrastructure and lacks native satellite imagery at high zoom levels across rural India.

## Decision
Adopt **Google Maps Platform** as the primary production provider for mobile and web, utilizing restricted public API keys (HTTP referrer and Android SHA-1 restricted). Maintain Leaflet + OpenStreetMap as a lightweight developer fallback for local offline testing.

## Consequences
- **Positive:** Immediate access to satellite imagery, turn-by-turn road routing, and high uptime.
- **Negative:** Commercial API usage incurs metered costs; requires strict quota limits and client-side key restrictions.
