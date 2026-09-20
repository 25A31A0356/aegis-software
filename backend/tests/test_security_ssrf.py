"""
AEGIS UNIFIED DATA CORE - SSRF Security Tests
Verifies that malicious administrator-supplied API URLs targeting private networks,
localhost, loopbacks, or cloud metadata endpoints are strictly blocked.
"""
from backend.app.core.ssrf import SSRFGuard
from backend.app.core.encryption import SecretVault


def test_ssrf_blocks_localhost():
    is_safe, err = SSRFGuard.validate_url("http://localhost:8080/api/internal", allow_local_in_dev=False)
    assert is_safe is False
    assert "local/loopback" in err or "blocked" in err


def test_ssrf_blocks_loopback_ip():
    is_safe, err = SSRFGuard.validate_url("http://127.0.0.1:5432", allow_local_in_dev=False)
    assert is_safe is False
    assert "blocked" in err.lower() or "local" in err.lower()


def test_ssrf_blocks_private_subnets():
    # 10.0.0.1 (RFC 1918)
    is_safe, err = SSRFGuard.validate_url("http://10.0.0.1/status", allow_local_in_dev=False)
    assert is_safe is False

    # 192.168.1.1 (RFC 1918)
    is_safe, err = SSRFGuard.validate_url("http://192.168.1.1/admin", allow_local_in_dev=False)
    assert is_safe is False

    # 172.16.0.5 (RFC 1918)
    is_safe, err = SSRFGuard.validate_url("http://172.16.0.5/secrets", allow_local_in_dev=False)
    assert is_safe is False


def test_ssrf_blocks_cloud_metadata_endpoint():
    # AWS/GCP 169.254.169.254
    is_safe, err = SSRFGuard.validate_url("http://169.254.169.254/latest/meta-data/", allow_local_in_dev=False)
    assert is_safe is False
    assert "blocked" in err.lower()


def test_ssrf_allows_legitimate_public_apis():
    is_safe, err = SSRFGuard.validate_url("https://api.open-meteo.com/v1/forecast")
    assert is_safe is True
    assert err == ""

    is_safe, err = SSRFGuard.validate_url("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson")
    assert is_safe is True


def test_secret_vault_encryption_masking():
    secret = "AIzaSyD9873491823791283_TEST"
    encrypted = SecretVault.encrypt_secret(secret)
    assert encrypted != secret
    assert len(encrypted) > 20

    decrypted = SecretVault.decrypt_secret(encrypted)
    assert decrypted == secret

    masked = SecretVault.mask_secret(secret)
    assert masked.endswith("TEST")
    assert "****************" in masked
    assert "AIzaSy" not in masked
