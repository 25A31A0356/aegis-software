# AEGIS Community Incident Reports — Single Source of Truth

The **AEGIS Community Reports System** provides an authoritative, centralized pipeline for citizen hazard observations, damaged infrastructure tracking, and crowd-sourced ground-truth telemetry.

---

## 1. Single Source of Truth Architecture

```
                       [ Aegis Alert Mobile App ]
                              │
               (POST /api/v1/reports, Offline Sync)
                              ▼
                ┌───────────────────────────────┐
                │   AEGIS SOFTWARE (Gateway)   │
                │  - Spam & Coordinate Guard    │
                │  - Idempotency Deduplication  │
                │  - Auto Reverse-Geocoding     │
                │  - Expiry Calculation         │
                └───────────────┬───────────────┘
                                │
                                ▼
                   [ PostgreSQL / PostGIS DB ]
               (Authoritative Community Record)
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
            (Real-Time WebSocket)       (Activity Stream)
                    │                       │
                    ▼                       ▼
         [ Aegis Web Dashboard ]    [ Aegis Alert App ]
```

Neither Aegis Web nor Aegis App maintains separate or local copies of the authoritative community database. All clients read and write directly to Aegis Software.

---

## 2. Category Taxonomy

The following standardized public safety categories are supported:
- `FLOOD`: River floods, coastal inundation, canal breaches
- `WATERLOGGING`: Urban street water accumulation, flooded underpasses
- `BLOCKED_ROAD`: Tree blockages, fallen debris, road closures
- `FALLEN_TREE`: Fallen trees damaging powerlines or structures
- `LANDSLIDE`: Mountain debris, mudslides, slope failures
- `FIRE`: Structural fires, local brushfires, transformer explosions
- `SEVERE_WEATHER`: Hailstorms, gale winds, localized microbursts
- `DAMAGED_INFRASTRUCTURE`: Collapsed bridges, damaged embankments, sinkholes
- `ACCIDENT`: Multi-vehicle collisions, transport accidents
- `UNSAFE_AREA`: Live exposed electrical wires, gas leaks, structural hazards
- `OTHER`: General public safety observations

---

## 3. Report Lifecycle & Verification Status

```
   [Citizen Submission]
            │
            ▼
      [ ACTIVE ] ────────────── (Upvotes >= 3, Upvotes > 2x Downvotes) ──► [ VERIFIED_COMMUNITY ]
            │                                                                      │
            ▼                                                                      ▼
      [ EXPIRED ] (Auto after 24h - 72h)                                     [ RESOLVED ] (Official / Moderator Action)
```

### Verification Badges:
- `OFFICIAL`: Verified official alert issued by IMD, NDMA, CWC, or local district administration.
- `VERIFIED_COMMUNITY`: Citizen report confirmed by multiple trusted community observers or verified responders.
- `UNVERIFIED_COMMUNITY`: Newly submitted ground-truth observation pending community or official verification.

---

## 4. Offline Synchronization & Idempotency

When connectivity is lost, the mobile app creates a local queue of pending reports with a client-generated UUID `idempotency_key`.

When network reconnects:
1. Mobile app calls `POST /api/v1/reports/sync` with the queued items.
2. Aegis Software checks `idempotency_key` against existing database records.
3. Existing records are skipped; new records are safely stored, activity-logged, and broadcasted to Web and App clients.
