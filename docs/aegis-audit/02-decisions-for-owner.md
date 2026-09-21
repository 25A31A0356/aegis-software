# AEGIS ALERT — Decisions for Owner Approval (Max 10 Key Items)
The following 10 architectural and policy decisions require formal confirmation from the project owner. Each decision includes a recommended production-ready default based on the Master Engineering Specification.

---

### Decision 1: Primary Map & Satellite Provider
- **Options:**
  1. *(Recommended)* **Google Maps Platform (Hybrid)**: High-resolution Indian satellite imagery, accurate road routing, verified official India boundary rendering.
  2. **MapMyIndia / Mappls**: Strong local Indian POI geocoding, official national cartography.
  3. **MapLibre GL + Licensed Tiles (OSM / Stadia / MapTiler)**: Open-source client with commercial tile backend.
- **Recommended Default:** **Google Maps Platform** for production mobile and web maps, with Leaflet/OpenStreetMap as local development fallback.

---

### Decision 2: Official Hazard & Weather Data Sources
- **Options:**
  1. *(Recommended)* **Multi-Tier Ingestion**: Open-Meteo for meteorological telemetry + NDMA SACHET (CAP 1.2 RSS) for national disaster alerts + USGS for seismic data.
  2. **Direct IMD & CWC API Integration**: Requires bilateral institutional data sharing agreements with Indian government agencies.
- **Recommended Default:** Multi-Tier Ingestion with strict `sourceTier` labeling (`OFFICIAL_IN` for NDMA/IMD, `MODEL_DERIVED` for Open-Meteo).

---

### Decision 3: SOS Notification Radius & "Authorized Nearby User" Definition
- **Options:**
  1. *(Recommended)* **10 km Default Radius (Configurable 5–20 km)**: Great-circle distance query to verified, opted-in responders and local emergency services.
  2. **District-Wide Broadcast**: Notify all registered users within the administrative district.
- **Recommended Default:** **10 km Great-Circle Radius** (`SOS_NOTIFY_RADIUS_KM=10`) using PostGIS spatial indexing. Never broadcast globally.

---

### Decision 4: Citizen Incident Report Visibility & Moderation Policy
- **Options:**
  1. *(Recommended)* **Community Visibility with Post-Moderation**: Visible to authenticated users within the same district; auto-flagged if downvoted or reported; administrative hide control.
  2. **Strict Pre-Moderation**: Reports remain hidden until manually approved by a designated dispatcher.
- **Recommended Default:** **Community Visibility with Post-Moderation** to maximize real-time situational awareness during active disasters.

---

### Decision 5: Data Retention & Privacy Policy (India DPDP Act 2023)
- **Options:**
  1. *(Recommended)* **30-Day SOS Location Retention**: Active GPS breadcrumbs retained for 30 days post-resolution for audit/rescue verification, then permanently purged. Non-SOS location tracking never persisted server-side.
  2. **90-Day Retention**: Extended retention for legal and disaster analysis.
- **Recommended Default:** **30-Day Post-Resolution Purge** for SOS location points; zero long-term retention for passive user coordinates.

---

### Decision 6: Emergency SMS & WhatsApp Gateway Provider
- **Options:**
  1. *(Recommended)* **Twilio / Gupshup / Fast2SMS (DLT Compliant)**: Enterprise SMS gateway configured with pre-approved TRAI DLT Principal Entity and Header IDs.
  2. **AWS SNS / Firebase Phone Auth**: Push and basic SMS notification.
- **Recommended Default:** **Gupshup / Twilio** with mandatory DLT Unicode template registration for English, Hindi, and Telugu.

---

### Decision 7: Responder Vetting & Verification Process
- **Options:**
  1. *(Recommended)* **Government Identity & Volunteer Organization Vetting**: Responders undergo document verification (Aadhaar / Civil Defense / Red Cross / Aapda Mitra ID) before receiving `VERIFIED_RESPONDER` role.
  2. **Open Community Responder**: Any registered user can opt-in to receive nearby emergency notifications.
- **Recommended Default:** **Verified Responders Only** for victim medical/blood group disclosure and nearby dispatch notifications (fail-closed for privacy).

---

### Decision 8: Official Emergency Services (112 / Police / NDRF) Handoff
- **Options:**
  1. *(Recommended)* **`NotIntegrated` Gateway with One-Tap 112 Dialer**: Launches user-confirmed device dialer to `112` with clear disclaimer ("Emergency services not automatically notified — tap to call 112").
  2. **Direct API Dispatch to State ERSS (Emergency Response Support System)**: Requires formal MoU with State Police / Ministry of Home Affairs.
- **Recommended Default:** **`NotIntegrated` One-Tap Dialer** until formal institutional integration is contracted.

---

### Decision 9: Platform Geofence & Scope Outside India
- **Options:**
  1. *(Recommended)* **India Geofenced Hazards + Global SOS/SAFE**: Hazard warnings and district search restricted to Indian territory; emergency SOS/SAFE check-ins to family work globally.
  2. **Strict Complete Geoblocking**: Entire application disabled outside Indian coordinates.
- **Recommended Default:** **India-Scoped Hazards & Maps, Unrestricted Family SOS/SAFE Notifications**.

---

### Decision 10: Advisory AI/ML Models & Safety Kill-Switches
- **Options:**
  1. *(Recommended)* **Advisory Only with Master Kill-Switch**: AI models used solely for report deduplication and voice intent parsing. Never in the SOS critical path; never generating unverified hazard text.
  2. **Fully Automated Disaster Severity Rating**: LLM automatically rates and summarizes community disaster reports.
- **Recommended Default:** **Advisory Only with Master Kill-Switch** (`ENABLE_AI_SYNTHESIS=false` in emergency critical paths).
