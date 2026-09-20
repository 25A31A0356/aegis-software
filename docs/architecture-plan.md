# AEGIS ALERT: Diagrammatic Technical Implementation Plan

Comprehensive diagrammatic architecture, lifecycle models, data flows, and verification matrix for the **AEGIS** (*Autonomous Emergency Grid & Intelligence System*) multi-hazard disaster early-warning and life-safety operations platform.

---

## 1. System Architecture & Workspaces Overview

```mermaid
flowchart TB
    subgraph INGESTION ["📡 Multi-Source Telemetry & Sensor Ingestion"]
        IMD["IMD Radar & Cyclone Feeds"]
        CWC["CWC River Gauges & Dam Levels"]
        CPCB["CPCB Air Quality Index (NAQI)"]
        INCOIS["INCOIS Tsunami & Coastal Swell"]
        USGS["USGS Seismic Network"]
        NASA["NASA FIRMS Thermal Fire Hotspots"]
        METEO["Open-Meteo High-Resolution NWP"]
    end

    subgraph WORKSPACE_1 ["🛡️ Workspace 1: aegis-software (Backend & AI Gateway)"]
        direction TB
        Adapter["Ingestion Pipeline & Heuristic Field Detector"]
        Correlator["Multi-Hazard Correlation Engine (Risk 0–100)"]
        Physics["Physics Models (Mohr-Coulomb, SCS-CN, CAPE, sWBGT)"]
        AI_Layer["Gemini 1.5 Flash AI Context Synthesizer"]
        SOS_Engine["Rapido-Style Geospatial SOS Matcher"]
        DB[(PostgreSQL 16 + PostGIS)]
        Cache[(Redis 7.0 In-Memory Cache)]
        WS_Broker["Realtime WebSocket & SSE Broker"]
        
        Adapter --> Correlator
        Correlator --> Physics
        Physics --> DB
        Physics --> Cache
        Correlator --> AI_Layer
        SOS_Engine <--> DB
        SOS_Engine --> WS_Broker
    end

    subgraph WORKSPACE_2 ["💻 Workspace 2: Aegis-web (Command Center)"]
        direction TB
        Dash["National Situation Dashboard"]
        GIS["Leaflet Tactical Map (8 Hazard Layers)"]
        Triage["SOS Dispatch & Incident Room"]
        Reports_Mod["Community Reports Moderation Queue"]
        Admin_Panel["Data Core Admin & Provider Health"]
    end

    subgraph WORKSPACE_3 ["📱 Workspace 3: aegis-alert (Mobile Client)"]
        direction TB
        SOS_Btn["1-Tap Emergency SOS (GPS + Battery + Triage)"]
        Voice_SOS["8-Language Spoken Voice SOS Parser"]
        Volunteer_Modal["Nearby SOS Responder Modal (45s Timer)"]
        Safe_Checkin["1-Tap 'I Am Safe' Family Broadcast"]
        Offline_Manual["Offline First-Aid & Evacuation Guides"]
    end

    subgraph HARDWARE_EDGE ["📻 Cyber-Physical Hardware Extension (AegisBeacon)"]
        ESP32["ESP32 Dual-Core MCU"]
        LoRa["SX1262 868MHz LoRa Transceiver"]
        Siren["120dB Piezo Acoustic Horn"]
        Strobe["48-LED Optical Flasher"]
        Solar["Solar Panel + LiFePO4 Battery (75-Day Standby)"]
    end

    INGESTION --> Adapter
    WS_Broker <==>|Bi-directional WebSocket / REST| WORKSPACE_2
    WS_Broker <==>|WebSocket / REST / Push| WORKSPACE_3
    WORKSPACE_3 -.->|Sub-GHz Radio Mesh| HARDWARE_EDGE
```

---

## 2. Real-Time Data Ingestion, Fusion & Threat Pipeline

```mermaid
flowchart LR
    subgraph Stage1 ["1. Ingestion & Validation"]
        RawData["Raw Agency Feeds (JSON/XML/GeoJSON)"]
        Validator["Moving Z-Score Anomaly Filter (|Z| > 3.5)"]
        Deduplicator["Spatial-Temporal Deduplicator (5km / 30min)"]
    end

    subgraph Stage2 ["2. Physics & Threat Scoring"]
        Runoff["SCS-CN Runoff Model"]
        Slope["Mohr-Coulomb Slope Stability"]
        Convective["CAPE Thunderstorm Updrafts"]
        Fusion["Composite Risk Formula (0–100)"]
    end

    subgraph Stage3 ["3. Dynamic Distribution"]
        Polygon["Precision Polygon Geofencer"]
        WS_Push["WebSocket Emergency Broadcast"]
        FCM["FCM / Expo Push Notifications"]
        SMSService["Emergency SMS Gateway"]
    end

    RawData --> Validator
    Validator --> Deduplicator
    Deduplicator --> Runoff & Slope & Convective
    Runoff & Slope & Convective --> Fusion
    Fusion --> Polygon
    Polygon --> WS_Push & FCM & SMSService
```

---

## 3. Rapido-Style Geospatial SOS Dispatch Lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor Victim as Trapped Citizen (Mobile App)
    participant Gateway as FastAPI Gateway (/api/v1/sos)
    participant Matcher as Geospatial Matching Engine
    participant DB as PostgreSQL Database
    participant Hub as RealtimeHub (WebSocket)
    actor Responder as Nearby Volunteer / NDRF Unit
    actor Dispatcher as Incident Commander (Web Console)

    Victim->>Gateway: POST /api/v1/sos (lat, lng, flash_flood, 3 victims)
    Gateway->>DB: INSERT aegis_sos_signals (Status: TRIGGERED, Priority: 92)
    Gateway->>Hub: Broadcast SOS_SIGNAL_CREATED
    Hub-->>Dispatcher: Instant Sound Alert + Live Red Beacon on Command Console

    Gateway->>Matcher: Trigger Spatial Search (10 km Initial Radius)
    Matcher->>DB: Query UserPreference (is_responder_opted_in=True, is_available=True)
    Matcher->>DB: Calculate Haversine Distances & Exclude Busy Responders
    Matcher-->>Gateway: 3 Candidates Found within 4.2 km
    Gateway->>DB: INSERT aegis_sos_responder_candidates (Status: OFFERED)
    Gateway->>Hub: Push Targeted Dispatch Offer to Responders

    Hub-->>Responder: In-App Sound + NearbySosRequestModal (45s Countdown)
    Responder->>Gateway: POST /api/v1/sos/:id/respond (Action: ACCEPT)
    Gateway->>DB: Atomic Update (Status: ACCEPTED, Assigned: Responder_1)
    Gateway->>Hub: Broadcast SOS_ACCEPTED (ETA: 6 mins)
    Hub-->>Victim: Victim Screen: Volunteer Mohan is En Route (4.2 km)

    loop Live GPS Stream (Every 5 seconds)
        Responder->>Gateway: POST /api/v1/sos/:id/responder-location (lat, lng, eta)
        Gateway->>Hub: Broadcast SOS_RESPONDER_MOVING
        Hub-->>Victim: Live Moving Marker on Tactical Map
        Hub-->>Dispatcher: Live Responder Tracking Corridor
    end

    Responder->>Gateway: POST /api/v1/sos/:id/on-site
    Gateway->>Hub: Broadcast SOS_ON_SITE
    Responder->>Gateway: POST /api/v1/sos/:id/resolve (Victims Safe)
    Gateway->>DB: Update Status: RESOLVED
    Gateway->>Hub: Broadcast SOS_RESOLVED
```

---

## 4. 4-Tier Zero-Internet Fallback Continuum

```mermaid
flowchart TD
    Start([Emergency Event Detected]) --> CheckNet{Internet / 4G Available?}

    CheckNet -- Yes --> TIER1["Tier 1: Cloud & WebSocket Real-Time Stream<br/>• Full GIS vector tiles<br/>• Bi-directional live dispatch<br/>• Realtime volunteer GPS breadcrumbs"]
    
    CheckNet -- Degraded --> TIER2["Tier 2: Encrypted Local Cache & SQLite<br/>• Offline action queuing<br/>• Cached emergency contacts & shelter locations<br/>• Auto-sync on reconnection"]

    CheckNet -- No Cellular Data --> TIER3["Tier 3: Native Hardware Telephony & GNSS SMS<br/>• Pre-filled emergency SMS with GPS coordinates<br/>• 1-tap direct dial to NDRF/112 intents<br/>• 100% zero-data communication"]

    CheckNet -- Total Blackout --> TIER4["Tier 4: Cyber-Physical Sub-GHz LoRa Mesh<br/>• 868.1 MHz long-range radio signal<br/>• 120dB acoustic horn + strobe array<br/>• Vernacular spoken voice instruction"]

    TIER1 --> Done([Citizen Protected & Rescue Dispatched])
    TIER2 --> Done
    TIER3 --> Done
    TIER4 --> Done
```

---

## 5. Database Architecture & Entity-Relationship Model (12 Core Tables)

```mermaid
erDiagram
    AEGIS_USERS ||--o{ AEGIS_INCIDENT_REPORTS : submits
    AEGIS_USERS ||--o{ AEGIS_SOS_SIGNALS : triggers
    AEGIS_USERS ||--o| AEGIS_USER_PREFERENCES : configures
    AEGIS_USERS ||--o{ AEGIS_REPORT_VOTES : casts
    AEGIS_USERS ||--o{ AEGIS_SOS_ASSIGNMENTS : responds

    AEGIS_HAZARD_EVENTS ||--o{ AEGIS_ALERTS : generates
    AEGIS_HAZARD_EVENTS ||--o{ AEGIS_ACTIVITY_EVENTS : emits

    AEGIS_SOS_SIGNALS ||--o{ AEGIS_SOS_OFFERS : creates
    AEGIS_SOS_SIGNALS ||--o{ AEGIS_SOS_RESPONDER_CANDIDATES : matches
    AEGIS_SOS_SIGNALS ||--o| AEGIS_SOS_ASSIGNMENTS : assigns

    AEGIS_INCIDENT_REPORTS ||--o{ AEGIS_REPORT_VOTES : receives
    AEGIS_INCIDENT_REPORTS ||--o{ AEGIS_ACTIVITY_EVENTS : emits

    AEGIS_USERS {
        string id PK
        string email UK
        string hashed_password
        string full_name
        string role
        string phone_number
        boolean is_active
        boolean is_verified
        datetime created_at
    }

    AEGIS_HAZARD_EVENTS {
        string id PK
        string external_id UK
        string source
        string category
        string severity
        string title
        text description
        float latitude
        float longitude
        float radius_km
        json polygon_coordinates
        float magnitude
        float wind_speed_kmh
        float water_level_m
        float precipitation_mm
        float confidence_score
        string status
        datetime occurs_at
        datetime expires_at
    }

    AEGIS_SOS_SIGNALS {
        string id PK
        string user_id FK
        float latitude
        float longitude
        float altitude
        float accuracy_meters
        string emergency_type
        string status
        float priority_score
        int victim_count
        text medical_notes
        string responder_id FK
        string responder_callsign
        float responder_lat
        float responder_lng
        int responder_eta_minutes
        int battery_level
        boolean is_synced_offline
        string idempotency_key UK
        datetime created_at
    }

    AEGIS_INCIDENT_REPORTS {
        string id PK
        string user_id FK
        string title
        text description
        string category
        string severity
        string verification_status
        boolean is_verified
        string source
        float latitude
        float longitude
        string location_name
        string city
        string district
        string state
        json media_urls
        int upvotes
        int downvotes
        string idempotency_key UK
        datetime created_at
    }

    AEGIS_SAFE_ZONES {
        string id PK
        string name
        string zone_type
        float latitude
        float longitude
        int capacity
        int current_occupancy
        string address
        string district
        string state
        string contact_phone
        boolean is_active
        json amenities
    }

    AEGIS_USER_PREFERENCES {
        string id PK
        string user_id FK
        json saved_locations
        json hazard_subscriptions
        boolean push_enabled
        boolean sms_alerts_enabled
        string language
        boolean is_responder_opted_in
        boolean is_available
        float last_known_lat
        float last_known_lng
        datetime last_location_time
        json emergency_contacts
    }

    AEGIS_DATA_SOURCES {
        string id PK
        string provider_code UK
        string name
        string base_url
        boolean is_active
        int poll_interval_minutes
        string auth_type
        text encrypted_credentials
        datetime last_polled_at
        string last_status
    }
```

---

## 6. Verification Plan & Test Automation Matrix (287 Tests)

```mermaid
flowchart LR
    subgraph QA1 ["Workspace 1: Backend (Pytest)"]
        T1["69 Tests Passing"]
        T1_Scope["• Auth & RBAC Security<br/>• Ingestion & SSRF Guards<br/>• Haversine SOS Matcher<br/>• Offline Sync & Replay"]
    end

    subgraph QA2 ["Workspace 2: Web (TSX / Vitest)"]
        T2["161 Tests Passing"]
        T2_Scope["• 8 GIS Layer Controls<br/>• Dispatch Triage Console<br/>• API Client Deduplication<br/>• Theme & Tokens"]
    end

    subgraph QA3 ["Workspace 3: Mobile (Vitest)"]
        T3["57 Tests Passing"]
        T3_Scope["• 1-Tap SOS Beacon Lifecycle<br/>• Offline SQLite Queue<br/>• 8-Language Voice Parser<br/>• SecureStore Token Handling"]
    end

    subgraph Summary ["Master Quality Gate"]
        Total["287 / 287 Passing (100% Pass Rate)"]
    end

    QA1 --> Summary
    QA2 --> Summary
    QA3 --> Summary
```
