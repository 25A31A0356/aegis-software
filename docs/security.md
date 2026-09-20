# AEGIS Unified Data Core — Security Architecture & Hardening

## 1. Security Design Principles

The AEGIS Unified Data Core is designed for mission-critical emergency infrastructure. Security is enforced through defense-in-depth across the network, application, cryptography, and persistence layers.

---

## 2. Server-Side Request Forgery (SSRF) Protection

When users or administrators register new API endpoints or run the Live API Tester, outbound HTTP requests are strictly mediated through `SSRFGuard` (`backend/app/core/ssrf.py`):

1. **Scheme Enforcement**: Only `http://` and `https://` protocols are allowed. `file://`, `gopher://`, `ftp://`, and other dangerous URI schemes are rejected immediately.
2. **DNS Resolution Verification**: The host domain is resolved via system DNS before socket connection.
3. **Blacklisted IP Ranges**: All resolved IP addresses are evaluated against forbidden CIDRs:
   - `0.0.0.0/8` (Current network)
   - `127.0.0.0/8` (Loopback addresses)
   - `10.0.0.0/8` (Private RFC 1918)
   - `172.16.0.0/12` (Private RFC 1918)
   - `192.168.0.0/16` (Private RFC 1918)
   - `169.254.0.0/16` (Link-Local & Cloud Metadata — e.g. `http://169.254.169.254/latest/meta-data/` for AWS/GCP/Azure)
   - `100.64.0.0/10` (Carrier-Grade NAT)
   - `::1/128`, `fc00::/7`, `fe80::/10` (IPv6 loopback & unique local addresses)

---

## 3. Cryptography & Secret Vault

### Encryption at Rest

All third-party API credentials, bearer tokens, and custom authorization headers stored in the PostgreSQL database are encrypted at rest using **Fernet (AES-128-CBC + HMAC-SHA256 authenticated encryption)** via `SecretVault` (`backend/app/core/encryption.py`):

- `ENCRYPTION_KEY` is derived from a 32-byte cryptographic secret configured strictly via environment variables.
- Secret keys are never serialized into JSON responses or returned in administrative list endpoints.

### Masking & Log Redaction

- When secrets are displayed in the Admin Console or API responses, they are deterministically masked:

  ```text
  Original:  IMD_RADAR_PROD_KEY_998124_AB92
  Masked:    ****************AB92
  ```

- The structured logging handler automatically filters and redacts key patterns matching:
  - `Bearer eyJ...`
  - `password=...`, `secret=...`, `token=...`, `api_key=...`

---

## 4. Role-Based Access Control (RBAC) & Authentication

- **JWT Tokens**: Signed using `HS256` with expiration lifetimes enforced (1440 minutes default).
- **Password Hashing**: Cryptographic password hashing utilizing native `bcrypt` with work factor 12.
- **Roles & Permissions**:
  - `ADMIN`: Full access to data source registration, field mapping studio, API testing, and audit logs.
  - `OFFICIAL` / `SDRF_OFFICER`: Access to raw/normalized observation telemetry, alert dispatch, and correlation matrix.
  - `CITIZEN`: Read-only access to public normalized weather, hazard maps, active alerts, and SOS dispatch.

---

## 5. Security Audit Logging

All administrative mutations (source registration, mapping edits, alert broadcasts, token creation) generate immutable records in the `audit_logs` table containing:

- `action`: e.g. `CREATE_SOURCE`, `UPDATE_MAPPING`, `TRIGGER_INGESTION`.
- `actor_id`: User UUID or `SYSTEM_SCHEDULER`.
- `client_ip`: Remote IP address extracted from `X-Forwarded-For`.
- `details`: JSON payload of modified attributes (with secrets stripped).
- `timestamp`: UTC timestamp with microsecond resolution.
