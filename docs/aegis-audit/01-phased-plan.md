# AEGIS ALERT — Phased Implementation Plan (Phases 1 to 8)
**Execution Strategy:** Sequential small verified increments with risk classification per task.

---

## Phase 1: Foundation Hardening & Hygiene
*Focus: Configuration validation, RBAC enforcement, global error handling, forbidden-pattern cleanup, terminology purge.*

- [ ] **Task 1.1: Environment & Config Validation** (`Risk: Medium`)
  - Enforce startup validation in `backend/app/core/config.py`: refuse production startup if default secrets or wildcard CORS are detected.
- [ ] **Task 1.2: Global Error Envelope & Friendly Messaging** (`Risk: Low`)
  - Standardize error responses into `{ "error": { "code": "...", "messageKey": "...", "requestId": "..." } }`.
  - Ensure stack traces and internal database errors are logged securely on the server and never leaked to clients.
- [ ] **Task 1.3: Terminology Purge ("SOS Grid" → "SOS MAP" / "SAFE PLAN MAP")** (`Risk: Low`)
  - Replace all remaining instances of `sos-grid`, `sosGrid`, and `SOS_GRID` across mobile, web, and docs (Iron Rule R9).
- [ ] **Task 1.4: Fake Data Isolation** (`Risk: Medium`)
  - Wrap all mock and demo datasets behind explicit `ENABLE_DEV_MOCKS=true` guards. In production, return honest empty states (*"No data available"*).

---

## Phase 2: Location, Maps, Weather & Hazards
*Focus: PostGIS geocoding, official hazard ingestion, resilient weather caching, India boundary compliance.*

- [ ] **Task 2.1: PostGIS District & Locality Geometry Optimization** (`Risk: Medium`)
  - Load authoritative Census/LGD district boundary dataset into PostGIS with spatial GiST indexing.
- [ ] **Task 2.2: Map & Satellite Provider Integration** (`Risk: Medium`)
  - Standardize map controls across web and mobile using official India-compliant boundary settings (ADR-001).
- [ ] **Task 2.3: Weather Cache & Circuit Breaker** (`Risk: Low`)
  - Implement grid-cell caching (TTL: 15 mins) with stale-while-revalidate pattern for Open-Meteo telemetry.
- [ ] **Task 2.4: Official Hazard Ingestion Connector (NDMA SACHET / CAP 1.2)** (`Risk: High`)
  - Build scheduled ingestion worker for CAP XML RSS feeds, normalizing polygons and publishing `hazard.updated` events.

---

## Phase 3: SOS, SAFE, Family Contacts & Realtime Pipeline
*Focus: Transactional SOS lifecycle, great-circle responder dispatch, multi-channel notification outbox, SSE/WebSocket streams.*

- [ ] **Task 3.1: Transactional Outbox for Emergency Events** (`Risk: High`)
  - Ensure SOS signal creation, initial GPS point, status history, and outbox rows are committed within a single atomic database transaction.
- [ ] **Task 3.2: Great-Circle Responder Radius Queries** (`Risk: Medium`)
  - Implement PostGIS `ST_DWithin` spatial query (default 10km radius) to identify active verified responders without global broadcasts.
- [ ] **Task 3.3: Family Contact Notification Queue** (`Risk: High`)
  - Process all registered emergency contacts independently (one contact failure never blocks others).
- [ ] **Task 3.4: Realtime Event Hub Hardening** (`Risk: Medium`)
  - Enforce token handshake and channel-level authorization on SSE (`/api/v1/events`) and WebSocket connections.

---

## Phase 4: Citizen Reports & Recent Activity Feed
*Focus: Incident reporting, EXIF stripping, community verification, audit logging.*

- [ ] **Task 4.1: Citizen Report Submission & Image Processing** (`Risk: Medium`)
  - Validate coordinates, strip EXIF metadata (GPS/device info) from uploaded evidence photos, and assign district codes server-side.
- [ ] **Task 4.2: Realtime Activity Feed** (`Risk: Low`)
  - Publish verified incident and disaster events to the `activity_events` stream for live dashboard consumption.

---

## Phase 5: Localization, Voice Assistant & Responsive UI/UX Polish
*Focus: 10 Indian languages, voice command grammar, WCAG AA accessibility, cross-device QA.*

- [ ] **Task 5.1: Localization Completeness & ICU Formatting** (`Risk: Low`)
  - Verify 100% string coverage across all 10 languages (English, Hindi, Telugu, Tamil, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi).
- [ ] **Task 5.2: Voice Assistant Emergency Grammar** (`Risk: Medium`)
  - Validate local speech-to-text / text-to-speech intent handlers for voice-triggered SOS with safety confirmation.
- [ ] **Task 5.3: Cross-Device UI Verification** (`Risk: Low`)
  - Audit layouts at 360px, 768px, 1024px, 1280px, 1440px, and 1920px breakpoints.

---

## Phase 6: Security Hardening & Privacy (DPDP Act Compliance)
*Focus: Token security, IDOR prevention, STRIDE mitigations, data retention policies.*

- [ ] **Task 6.1: Secure Cookie Authentication for Web** (`Risk: High`)
  - Migrate web auth from `localStorage` to `httpOnly + Secure + SameSite=Strict` cookies with CSRF tokens.
- [ ] **Task 6.2: DPDP Act 2023 Consent & Retention Engine** (`Risk: High`)
  - Implement automated retention cleaner (purge SOS breadcrumb points N days post-resolution; purge non-SOS location tracking).

---

## Phase 7: Analytics & Advisory AI/ML
*Focus: Incident clustering, false report scoring, KPI dashboards.*

- [ ] **Task 7.1: Privacy-Preserving Analytics Aggregation** (`Risk: Medium`)
  - Build aggregated spatial views (H3 / geohash grid with k>=5 anonymity threshold) for emergency dispatch metrics.
- [ ] **Task 7.2: Advisory ML False-Report Scoring** (`Risk: Low`)
  - Feature-flagged advisory scoring for incident moderation queue (strictly out of the emergency SOS critical path).

---

## Phase 8: Full Verification, Documentation & Release Checklist
*Focus: V1–V12 test execution, final audit report, operational runbooks.*

- [ ] **Task 8.1: End-to-End Test Suite Execution (V1–V12)** (`Risk: Low`)
  - Run full automated test suite, capture evidence logs and database state proofs.
- [ ] **Task 8.2: Final Delivery Package & Operations Manual** (`Risk: Low`)
  - Compile final release documentation, migration guides, and owner action checklist.
