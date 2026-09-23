# AEGIS Master API Specification (OpenAPI v1)

## Base URL: `/api/v1`

### Endpoints
1. `GET /api/v1/weather?lat={lat}&lon={lon}` - Live weather with data provenance and freshness envelope.
2. `GET /api/v1/correlation/decoupled-risk?lat={lat}&lon={lon}` - Independent 3-factor risk analysis.
3. `POST /api/v1/sos/` - Idempotent SOS creation with GPS accuracy and victim count.
4. `GET /api/v1/sos/active-map` - Active distress map filtered by `active_map_visibility_until`.
5. `POST /api/v1/sos/{id}/accept` - Atomic responder dispatch matching.
