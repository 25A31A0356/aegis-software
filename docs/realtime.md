# AEGIS Real-Time Synchronization & Event Engine

Aegis Software provides dual-protocol real-time streaming:

1. **WebSocket Gateway**: `ws://localhost:8000/api/v1/ws` (Bidirectional low-latency event channel)
2. **Server-Sent Events (SSE)**: `http://localhost:8000/api/v1/activity/stream` (Unidirectional lightweight HTTP stream)

---

## 1. WebSocket Protocol & Handshake

### Connection Endpoint

```text
ws://<AEGIS_HOST>:8000/api/v1/ws?client=web&client_key=<AEGIS_WEB_CLIENT_KEY>
```

### Initial Server Welcome Packet

```json
{
  "event": "CONNECTED",
  "service": "AEGIS Real-Time Gateway",
  "version": "2.4.0",
  "client_type": "web",
  "timestamp": "2026-09-19T18:00:00.000Z",
  "available_channels": ["all", "reports", "hazards", "sos"]
}
```

### Channel Subscriptions

Clients can dynamically filter which events they receive:

```json
// Client -> Server: Subscribe to Community Reports
{
  "type": "subscribe",
  "channel": "reports"
}

// Client -> Server: Ping Heartbeat
{
  "type": "ping"
}
```

---

## 2. Event Types & Schemas

### `REPORT_CREATED`

Broadcasted immediately when a new community report is submitted:

```json
{
  "event": "REPORT_CREATED",
  "category": "COMMUNITY_REPORT",
  "channel": "reports",
  "timestamp": "2026-09-19T18:01:23.456Z",
  "data": {
    "id": "rep_99e7c8d6",
    "category": "FLOOD",
    "title": "Severe Waterlogging on Ring Road",
    "description": "Knee-deep water accumulation causing heavy traffic gridlock",
    "severity": "HIGH",
    "status": "ACTIVE",
    "verification_status": "UNVERIFIED_COMMUNITY",
    "is_verified": false,
    "source": "COMMUNITY",
    "latitude": 28.6139,
    "longitude": 77.2090,
    "location_name": "Ring Road Underpass",
    "city": "New Delhi",
    "state": "Delhi",
    "upvotes": 0,
    "downvotes": 0,
    "created_at": "2026-09-19T18:01:23.000Z"
  }
}
```

### `REPORT_UPDATED` / `REPORT_VERIFIED`

Broadcasted when community upvoting elevates trust score or a moderator updates status:

```json
{
  "event": "REPORT_VERIFIED",
  "category": "COMMUNITY_REPORT",
  "channel": "reports",
  "timestamp": "2026-09-19T18:05:00.000Z",
  "data": {
    "id": "rep_99e7c8d6",
    "status": "ACTIVE",
    "verification_status": "VERIFIED_COMMUNITY",
    "is_verified": true,
    "upvotes": 3,
    "downvotes": 0
  }
}
```

### `HAZARD_CREATED` / `HAZARD_UPDATED`

Broadcasted when automated provider ingestion (USGS, Open-Meteo, NASA FIRMS, IMD, CWC) detects new seismic, thermal, cyclone, or hydrological anomalies.

### `SOS_CREATED`

Broadcasted when an emergency SOS distress beacon is dispatched from Aegis App (PII strictly redacted for public subscribers).

---

## 3. Privacy & PII Sanitization

The `EventBroker` automatically scrubs private caller phone numbers, emails, user IDs, and password hashes before broadcasting event packets across public WebSocket and SSE channels.
