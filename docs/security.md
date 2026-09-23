# AEGIS Security Framework & 54-Point Audit

## Security Baseline
- **OWASP ASVS 5.0** & **OWASP MASVS** compliant.
- Strict TLS 1.3 in transit, AES-256 (KMS) at rest.
- Role-Based Access Control (RBAC) enforced server-side.
- Phone number masking on public SOS dispatch maps.
- All media uploads verified by MIME magic-bytes and stored with randomized S3 keys.
