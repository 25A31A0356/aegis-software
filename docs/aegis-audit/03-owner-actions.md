# AEGIS ALERT — Owner Actions (Real-World Prerequisites)
The following tasks cannot be performed by code alone and require executive, administrative, or legal action from the project owner.

---

## 1. TRAI DLT Registration for Indian SMS & Emergency Notifications
- [ ] **Principal Entity Registration:** Register the enterprise entity on an Indian Telecom DLT portal (e.g., Jio DLT, Airtel DLT, VilPower).
- [ ] **Sender Header / ID Approval:** Obtain approved 6-character alphabetic Sender Headers (e.g., `AEGISX`, `AEGSOS`).
- [ ] **SMS Content Template Approval:** Submit and approve multi-lingual transactional emergency templates (English, Hindi, Telugu, Tamil):
  - *SOS Emergency Template:* `{#var#} triggered SOS at {#var#}. Location: {#var#}. Immediate assistance requested. Details: {#var#}`
  - *SAFE Check-in Template:* `{#var#} is SAFE. Current location: {#var#}. {#var#}`
- [ ] **URL Whitelisting:** Register the official short-link domain (e.g., `https://aegis.in/s/{token}`) on the DLT portal.

---

## 2. Commercial Cloud & API Provider Accounts
- [ ] **Google Maps Platform:**
  - Create Google Cloud project, enable Maps SDK for Android/iOS, Maps JavaScript API, Geocoding API, and Directions API.
  - Configure HTTP referrer restrictions for web and SHA-1 certificate fingerprint restrictions for mobile packages.
  - Set up budget alerts and daily request quotas.
- [ ] **External Hazard & Meteorological Feeds:**
  - Submit request for official NDMA SACHET API credentials / verify public CAP 1.2 RSS endpoints.
  - Verify commercial usage terms for Open-Meteo meteorological endpoints.
- [ ] **Push Notification Services:**
  - Configure Firebase Cloud Messaging (FCM) project and Apple Developer APNs credentials.

---

## 3. Mobile App Store Declarations (Google Play & Apple App Store)
- [ ] **Google Play Console Declarations:**
  - Submit **Background Location Declaration** detailing the emergency rescue tracking use case.
  - Submit **Foreground Service (Location)** permission declaration for active SOS breadcrumb tracking.
  - Declare SMS/Dialer emergency intentions (`SEND_SMS` restricted; confirm user-initiated prefilled composer flow).
- [ ] **Apple App Store Connect:**
  - Complete App Privacy nutrition labels (location linked to user for emergency rescue, contact info, diagnostics).
  - Configure `UIBackgroundModes` for location updates during active emergency sessions.

---

## 4. Legal Review & DPDP Act 2023 Compliance
- [ ] **Privacy Policy & Terms of Service:** Have certified legal counsel review data retention policies, itemized user consents (location, blood group, emergency contacts), and grievance redressal mechanisms in compliance with the Digital Personal Data Protection (DPDP) Act 2023.
- [ ] **Designate Data Protection Officer (DPO):** Publish contact details for user data grievance and deletion requests.

---

## 5. Emergency Services & Responder Vetting Framework
- [ ] **Standard Operating Procedure (SOP) for Responder Onboarding:** Define official documentation required to verify emergency volunteers and medical responders.
- [ ] **Institutional Outreach (Optional):** Initiate dialogue with State Disaster Management Authorities (SDMA) or 112 ERSS for future direct dispatch integration.
